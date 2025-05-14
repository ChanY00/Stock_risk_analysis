import re
from collections import Counter


def extract_top_keywords(texts, top_n=4):
    words = []
    for t in texts:
        words.extend(re.findall(r"[가-힣]+", t))
    return [w for w,_ in Counter(words).most_common(top_n)]