"""County-level geo enrichment for PA mentions.

When an entity match fails, tries to geolocate the mention to a PA county
using a county/city/zip lookup table. Catches incidents like
"Mechanicsburg water system offline" even without an exact entity match.
"""

import re

from .utils.text import normalize_text

# PA counties and their major cities/boroughs/townships
# This allows geo-enrichment when no entity match is found
PA_COUNTY_PLACES: dict[str, list[str]] = {
    "Adams": ["gettysburg", "biglerville", "littlestown", "new oxford", "east berlin", "fairfield"],
    "Allegheny": ["pittsburgh", "mckeesport", "penn hills", "ross", "shaler", "plum", "bethel park",
                   "mount lebanon", "upper st clair", "north allegheny", "monroeville"],
    "Beaver": ["beaver", "beaver falls", "aliquippa", "ambridge", "rochester"],
    "Berks": ["reading", "wyomissing", "shillington", "kutztown", "hamburg", "boyertown"],
    "Blair": ["altoona", "hollidaysburg", "tyrone", "duncansville"],
    "Bradford": ["towanda", "sayre", "athens", "troy"],
    "Bucks": ["doylestown", "levittown", "bristol", "quakertown", "newtown", "perkasie",
              "warminster", "bensalem", "langhorne"],
    "Butler": ["butler", "cranberry", "zelienople", "slippery rock", "mars"],
    "Cambria": ["johnstown", "ebensburg", "portage", "cresson"],
    "Carbon": ["jim thorpe", "lehighton", "palmerton", "nesquehoning"],
    "Centre": ["state college", "bellefonte", "philipsburg", "boalsburg"],
    "Chester": ["west chester", "coatesville", "downingtown", "phoenixville", "malvern",
                "kennett square", "oxford"],
    "Clinton": ["lock haven", "mill hall", "renovo"],
    "Columbia": ["bloomsburg", "berwick", "centralia"],
    "Crawford": ["meadville", "titusville", "conneaut lake"],
    "Cumberland": ["carlisle", "mechanicsburg", "camp hill", "new cumberland", "shippensburg",
                    "lemoyne", "wormleysburg", "east pennsboro", "hampden"],
    "Dauphin": ["harrisburg", "hershey", "hummelstown", "middletown", "steelton",
                "lower swatara", "derry", "swatara", "lower paxton", "susquehanna",
                "paxtang", "penbrook", "highspire", "royalton", "elizabethville",
                "lykens", "gratz", "williamstown", "millersburg"],
    "Delaware": ["chester", "media", "upper darby", "haverford", "springfield",
                 "marple", "radnor", "swarthmore", "drexel hill"],
    "Erie": ["erie", "corry", "edinboro", "girard", "north east"],
    "Fayette": ["uniontown", "connellsville", "brownsville", "masontown"],
    "Franklin": ["chambersburg", "waynesboro", "greencastle", "mercersburg"],
    "Fulton": ["mcconnellsburg"],
    "Greene": ["waynesburg"],
    "Huntingdon": ["huntingdon", "mount union"],
    "Indiana": ["indiana", "blairsville", "homer city"],
    "Jefferson": ["brookville", "punxsutawney", "reynoldsville"],
    "Juniata": ["mifflintown", "port royal"],
    "Lackawanna": ["scranton", "dunmore", "old forge", "carbondale", "clarks summit"],
    "Lancaster": ["lancaster", "lititz", "ephrata", "manheim", "elizabethtown",
                   "mount joy", "strasburg", "columbia", "quarryville"],
    "Lawrence": ["new castle", "ellwood city"],
    "Lebanon": ["lebanon", "palmyra", "myerstown", "cleona", "annville"],
    "Lehigh": ["allentown", "bethlehem", "emmaus", "macungie", "whitehall",
               "upper macungie", "lower macungie", "salisbury"],
    "Luzerne": ["wilkes-barre", "hazleton", "nanticoke", "pittston", "kingston",
                "edwardsville", "plymouth", "mountain top"],
    "Lycoming": ["williamsport", "montoursville", "muncy", "jersey shore"],
    "McKean": ["bradford", "kane", "smethport"],
    "Mercer": ["sharon", "hermitage", "grove city", "greenville"],
    "Mifflin": ["lewistown", "burnham"],
    "Monroe": ["stroudsburg", "east stroudsburg", "mount pocono", "tannersville"],
    "Montgomery": ["norristown", "conshohocken", "lansdale", "king of prussia",
                   "blue bell", "ambler", "abington", "cheltenham", "lower merion",
                   "upper merion", "plymouth meeting", "horsham"],
    "Montour": ["danville"],
    "Northampton": ["easton", "bethlehem", "nazareth", "bangor", "pen argyl",
                     "bath", "freemansburg", "northampton", "wind gap"],
    "Northumberland": ["sunbury", "shamokin", "mount carmel", "northumberland"],
    "Perry": ["new bloomfield", "newport", "duncannon", "marysville"],
    "Philadelphia": ["philadelphia", "philly"],
    "Pike": ["milford", "matamoras", "dingmans ferry"],
    "Potter": ["coudersport"],
    "Schuylkill": ["pottsville", "tamaqua", "shenandoah", "minersville"],
    "Snyder": ["selinsgrove", "middleburg"],
    "Somerset": ["somerset", "meyersdale", "berlin"],
    "Sullivan": ["laporte"],
    "Susquehanna": ["montrose"],
    "Tioga": ["wellsboro", "mansfield"],
    "Union": ["lewisburg", "mifflinburg"],
    "Venango": ["oil city", "franklin"],
    "Warren": ["warren", "youngsville"],
    "Washington": ["washington", "canonsburg", "mcmurray", "charleroi"],
    "Wayne": ["honesdale", "hawley"],
    "Westmoreland": ["greensburg", "latrobe", "jeannette", "irwin", "ligonier",
                      "mount pleasant", "murrysville"],
    "Wyoming": ["tunkhannock"],
    "York": ["york", "hanover", "red lion", "dallastown", "dover", "spring grove",
             "west york", "spring garden", "shrewsbury"],
}

# Pre-build a reverse lookup: place_name -> county
_PLACE_TO_COUNTY: dict[str, str] = {}
for _county, _places in PA_COUNTY_PLACES.items():
    for _place in _places:
        _PLACE_TO_COUNTY[_place] = _county
    # Also add the county name itself
    _PLACE_TO_COUNTY[_county.lower()] = _county


def enrich_county(text: str) -> str | None:
    """Try to identify a PA county from text content.

    Args:
        text: The raw text to search for geographic references.

    Returns:
        County name if found, None otherwise.
    """
    if not text:
        return None

    text_lower = normalize_text(text)

    # First, check for explicit "X County" mentions
    county_pattern = re.compile(r"(\w[\w\s]*?)\s+county", re.I)
    for match in county_pattern.finditer(text_lower):
        candidate = match.group(1).strip()
        # Check if it's a PA county
        for county in PA_COUNTY_PLACES:
            if candidate == county.lower():
                return county

    # Then, check for place names
    # Sort by length descending so "mount lebanon" matches before "mount"
    for place, county in sorted(_PLACE_TO_COUNTY.items(), key=lambda x: -len(x[0])):
        if place in text_lower:
            # Verify it's a word boundary match (not a substring of another word)
            pattern = rf"\b{re.escape(place)}\b"
            if re.search(pattern, text_lower):
                return county

    return None


def get_county_for_place(place_name: str) -> str | None:
    """Look up which county a place belongs to."""
    return _PLACE_TO_COUNTY.get(normalize_text(place_name))
