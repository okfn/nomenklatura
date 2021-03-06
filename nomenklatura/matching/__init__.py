import logging
import time

from nomenklatura.core import db
from nomenklatura.util import candidate_cache_key, cache_get, cache_set
from nomenklatura.model import Value

from nomenklatura.matching.normalize import normalize
from nomenklatura.matching.levenshtein import levenshtein
from nomenklatura.matching.fw import fw

log = logging.getLogger(__name__)

ALGORITHMS = {
        'levenshtein': levenshtein,
        'fuzzywuzzy': fw
    }

def get_algorithms():
    algorithms = []
    for name, fn in ALGORITHMS.items():
        algorithms.append((name, fn.__doc__))
    return algorithms

def _get_candidates(dataset):
    for value in Value.all(dataset, eager_links=dataset.match_links):
        candidate = normalize(value.value, dataset)
        yield candidate, value.id
        if dataset.match_links:
            for link in value.links_static:
                candidate = normalize(link.key, dataset)
                yield candidate, value.id

def get_candidates(dataset):
    from nomenklatura.util import candidate_cache_key
    #return set(_get_candidates(dataset))
    begin = time.time()

    key = candidate_cache_key(dataset)
    cand = cache_get(key)
    if cand is None:
        cand = list(set(_get_candidates(dataset)))
        cache_set(key, cand)

    duration = time.time() - begin
    log.info("Fetching %s candidates took: %sms",
            len(cand), duration*1000)
    return cand

def match(text, dataset, query=None):
    query = '' if query is None else query.strip().lower()
    text_normalized = normalize(text, dataset)
    candidates = get_candidates(dataset)
    matches = []
    begin = time.time()
    func = ALGORITHMS.get(dataset.algorithm, levenshtein)
    for candidate, value in candidates:
        if len(query) and query not in candidate.lower():
            continue
        score = func(text_normalized, candidate)
        matches.append((candidate, value, score))
    matches = sorted(matches, key=lambda (c,v,s): s, reverse=True)
    values = set()
    matches_uniq = []
    for c,v,s in matches:
        if v in values:
            continue
        values.add(v)
        matches_uniq.append((c,v,s))
    duration = time.time() - begin
    log.info("Matching %s candidates took: %sms",
            len(matches_uniq), duration*1000)
    return matches_uniq


