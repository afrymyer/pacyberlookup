"""SharePoint list integration for incident tracking."""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def push_to_sharepoint(incident: dict) -> bool:
    """Push an incident record to a SharePoint list.

    Uses the Office365-REST-Python-Client library when configured.

    Args:
        incident: The incident dict to push.

    Returns:
        True if successfully pushed.
    """
    if os.getenv("SHAREPOINT_ENABLED", "false").lower() != "true":
        logger.debug("SharePoint disabled; skipping push")
        return False

    site_url = os.getenv("SHAREPOINT_SITE_URL", "")
    list_name = os.getenv("SHAREPOINT_LIST_NAME", "PA Cyber Incidents")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID", "")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET", "")
    tenant_id = os.getenv("SHAREPOINT_TENANT_ID", "")

    if not all([site_url, client_id, client_secret, tenant_id]):
        logger.warning("SharePoint configuration incomplete; skipping push")
        return False

    try:
        from office365.runtime.auth.client_credential import ClientCredential
        from office365.sharepoint.client_context import ClientContext

        credentials = ClientCredential(client_id, client_secret)
        ctx = ClientContext(site_url).with_credentials(credentials)

        sp_list = ctx.web.lists.get_by_title(list_name)

        def _fmt_dt(dt):
            if isinstance(dt, datetime):
                return dt.isoformat()
            return str(dt) if dt else ""

        item_data = {
            "Title": incident.get("entity_name", "Unknown"),
            "DetectedAt": _fmt_dt(incident.get("detected_at")),
            "PublishedAt": _fmt_dt(incident.get("published_at")),
            "EntityName": incident.get("entity_name", ""),
            "MatchedAlias": incident.get("matched_alias", ""),
            "EntityType": incident.get("entity_type", ""),
            "County": incident.get("county", ""),
            "Headline": incident.get("headline", "")[:255],
            "Source": incident.get("source", ""),
            "SourceType": incident.get("source_type", ""),
            "URL": incident.get("url", ""),
            "IncidentType": incident.get("incident_type", ""),
            "Summary": (incident.get("ai_summary") or incident.get("summary", ""))[:500],
            "ConfidenceScore": str(incident.get("confidence_score", 0)),
            "ConfidenceBand": incident.get("confidence_band", ""),
            "Category": incident.get("category", ""),
            "VerificationStatus": incident.get("verification_status", "Unverified"),
            "RequiresAction": "Yes" if incident.get("requires_action") else "No",
            "MappedClientOrProspect": "Yes" if incident.get("mapped_client_or_prospect") else "No",
        }

        sp_list.add_item(item_data).execute_query()
        logger.info("SharePoint: pushed incident for %s", incident.get("entity_name"))
        return True

    except ImportError:
        logger.error("office365-rest-python-client not installed; cannot push to SharePoint")
        return False
    except Exception:
        logger.exception("Failed to push to SharePoint for: %s",
                         incident.get("entity_name", "Unknown"))
        return False
