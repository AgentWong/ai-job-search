from .ashby import fetch_jobs as ashby_fetch
from .bamboohr import fetch_jobs as bamboohr_fetch
from .breezy import fetch_jobs as breezy_fetch
from .careerpuck import fetch_jobs as careerpuck_fetch
from .comeet import fetch_jobs as comeet_fetch
from .dayforce import fetch_jobs as dayforce_fetch
from .eightfold import fetch_jobs as eightfold_fetch
from .gem import fetch_jobs as gem_fetch
from .greenhouse import fetch_jobs as greenhouse_fetch
from .isolvedhire import fetch_jobs as isolvedhire_fetch
from .lever import fetch_jobs as lever_fetch
from .oracle import fetch_jobs as oracle_fetch
from .pinpoint import fetch_jobs as pinpoint_fetch
from .polymer import fetch_jobs as polymer_fetch
from .recruitee import fetch_jobs as recruitee_fetch
from .smartrecruiters import fetch_jobs as smartrecruiters_fetch
from .rippling import fetch_jobs as rippling_fetch
from .trakstar import fetch_jobs as trakstar_fetch
from .workable import fetch_jobs as workable_fetch
from .workday import fetch_jobs as workday_fetch

PLATFORM_REGISTRY = {
    "ashby": ashby_fetch,
    "bamboohr": bamboohr_fetch,
    "breezy": breezy_fetch,
    "careerpuck": careerpuck_fetch,
    "comeet": comeet_fetch,
    "dayforce": dayforce_fetch,
    "eightfold": eightfold_fetch,
    "gem": gem_fetch,
    "greenhouse": greenhouse_fetch,
    "isolvedhire": isolvedhire_fetch,
    "lever": lever_fetch,
    "oracle": oracle_fetch,
    "pinpoint": pinpoint_fetch,
    "polymer": polymer_fetch,
    "recruitee": recruitee_fetch,
    "smartrecruiters": smartrecruiters_fetch,
    "rippling": rippling_fetch,
    "trakstar": trakstar_fetch,
    "workable": workable_fetch,
    "workday": workday_fetch,
}
