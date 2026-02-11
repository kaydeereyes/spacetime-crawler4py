import re
import hashlib
from urllib.parse import urlparse, urljoin, urldefrag, parse_qsl, urlencode, urlunparse
from bs4 import BeautifulSoup
from utils.response import Response
from collections import Counter, defaultdict

STOPWORDS = {
    "a","about","above","after","again","against","all","am","an","and","any","are","aren't","as","at",
    "be","because","been","before","being","below","between","both","but","by","can't","cannot","could",
    "couldn't","did","didn't","do","does","doesn't","doing","don't","down","during","each","few","for",
    "from","further","had","hadn't","has","hasn't","have","haven't","having","he","he'd","he'll","he's",
    "her","here","here's","hers","herself","him","himself","his","how","how's","i","i'd","i'll","i'm",
    "i've","if","in","into","is","isn't","it","it's","its","itself","let's","me","more","most","mustn't",
    "my","myself","no","nor","not","of","off","on","once","only","or","other","ought","our","ours",
    "ourselves","out","over","own","same","shan't","she","she'd","she'll","she's","should","shouldn't",
    "so","some","such","than","that","that's","the","their","theirs","them","themselves","then","there",
    "there's","these","they","they'd","they'll","they're","they've","this","those","through","to","too",
    "under","until","up","very","was","wasn't","we","we'd","we'll","we're","we've","were","weren't",
    "what","what's","when","when's","where","where's","which","while","who","who's","whom","why","why's",
    "with","won't","would","wouldn't","you","you'd","you'll","you're","you've","your","yours","yourself",
    "yourselves"
}

STRIP_KEYS = {
    "body","enddt","fbclid","format","gclid","ical","jsessionid","location",
    "outlook-ical","phpsessid","ref","ref_src","rrv","sessionid", "sid","startdt",
    "subject","utm_source","utm_medium","utm_campaign","utm_term","utm_content","view", "utm_",
    "session", "search", "keyword", "query", "auth", "ticket", "sso", "token", "share"
    ,"media","tok"
}

unique_urls = set()
longest_page = ("", 0) # (url, word_count)
word_frequencies = Counter()
seen_hashes = set()
subdomains = defaultdict(set)

LARGE_FILE_SIZE = 10_000_000
MIN_WORD_COUNT = 50

def save_report(filename = "report.txt"):
    """
    Saves report
    Runtime: O(n) for each word in word_frequencies and amount of domains.
    """
    with open("report.txt", "w") as f:
        #Q1
        f.write(f'Unique pages: {len(unique_urls)}\n')
        #Q2
        f.write(f'Longest page: {longest_page[0]} ({longest_page[1]} words)\n\n')
        #Q3
        f.write("Top 50 words:\n")
        for rank, (word, count) in word_frequencies.most_common(50):
            f.write(f"  {rank}. {word}: {count}\n")
        f.write("\n")
        #Q4
        f.write(f"\nSubdomains found: {len(subdomains)}\n")
        for sub in sorted(subdomains):
            f.write(f"  {sub}, {len(subdomains[sub])}\n")

    print(f"Report saved to {filename}")

def tokenize_text(text: str):
    """
    Tokenizes file into a list of Tokens.
    Runtime = O(m), where m is the number of tokens generated.
    """
    tokens = []
    token = ""

    for char in text.lower():
        if char.isalnum() and char.isascii():
            token += char
        else:
            if token:
                tokens.append(token)
                token = ""

    if token:
        tokens.append(token)

    return tokens

def normalize_url(url):
    """
    Cleans/Normalizes URL to remove trailing slashes, stripping tracking parameter,
    keeping calendar-related query params for event pages, 
    sorting remaining params for consistency
    """
    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    lower_path = path.lower()

    if any(segment in lower_path for segment in ("/event", "/events", "/talks/day", "/calendar", "/ical")):
        new_query = ""
    else:
        pairs = parse_qsl(parsed.query, True)
        kept_urls = [(k, v) for (k, v) in pairs if k.lower() not in STRIP_KEYS]
        
        if kept_urls:
            new_query = urlencode(sorted(kept_urls))
        else:
            new_query = ""

    normalized = urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, new_query, ""))
    return normalized

def scraper(url, resp):
    """
    Initiates Scraper, returning a list of valid hyperlinks.
    """
    links = extract_next_links(url, resp)
    save_report()
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    """
    Iniates the crawling. Parses HTML with Beautiful Soup, removing scripts and 
    leaving human-readable text. Tokenizes and filters stopwords and tracks the page
    with the most stopwords. Finds all links and normalizes them.
    """
    global longest_page
    hyperlinks = set()

    if 600 <= resp.status <= 608:
        print(f"Error: {resp.error}")
        return list(hyperlinks)

    if resp.status != 200:
        print(f"Error: {resp.error}")
        return list(hyperlinks)
    
    if not resp.raw_response or not resp.raw_response.content: # dead URLs
        return list(hyperlinks)
    
    if len(resp.raw_response.content) == 0: # no content
        return list(hyperlinks)
    
    if len(resp.raw_response.content) > LARGE_FILE_SIZE:
        return list(hyperlinks)
    
    if "text/html" not in resp.raw_response.headers.get("Content-Type", ""):
        return list(hyperlinks)
    
    
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    
    # Remove script and style elements so only visible page text is processed
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Extract text and tokenize for word count
    text = soup.get_text(separator=" ")
    tokens = tokenize_text(text)
    filtered = [t for t in tokens if t not in STOPWORDS]

    if len(tokens) < MIN_WORD_COUNT:
        return list(hyperlinks)
    
    # Hash urls, duplicate content check
    content_hash = hashlib.md5(" ".join(filtered).encode()).hexdigest()

    if content_hash in seen_hashes:
        return list(hyperlinks)
    
    seen_hashes.add(content_hash)

    # Q1: add the defragmented url to the set of unique urls
    page_url, _ = urldefrag(resp.url)
    unique_urls.add(page_url)

     # Q2: update longest_page if the current page has more words
    word_count = len(filtered)
    if word_count > longest_page[1]:
        longest_page = (page_url, word_count)

    # Q3: track word frequencies
    word_frequencies.update(filtered)

    # Q4: subdomains
    host = urlparse(page_url).hostname.lower()
    if host.endswith(".uci.edu"):
        subdomains[host].add(page_url)

    links = soup.find_all("a", href=True)

    for alink in links:
        link = urljoin(resp.url, alink["href"])
        clean_url, _ = urldefrag(link)
        normalized_url = normalize_url(clean_url)

        if not normalized_url: # skip
            continue
        if normalized_url == page_url:
            continue
        if not is_valid(normalized_url):
            continue

        hyperlinks.add(normalized_url)

    return list(hyperlinks)

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        
        host = (parsed.hostname or "").lower()
        allowed = [".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu"]

        if not any(host == suf.lstrip(".") or host.endswith(suf) for suf in allowed):
            return False
        
        path = parsed.path.lower()

        #DETECT TRAPS
        #calendars
        if re.search(r"/(calendar|date|year|month|archive|day)/\d{4}", path):
            return False
        if re.search(r"/events/.*/day/\d{4}-\d{2}-\d{2}/?$", path):
            return False
        if re.search(r"(outlook|calendar|ical|gcal|event|events)", path):
            return False

        # infinite queries
        if parsed.query:
            params = parsed.query.split("&")
            if len(params) > 5:
                return False

        # infinite directories
        if parsed.path.count("/") > 10:
            return False
        
        # repeated path segments
        segments = [s for s in parsed.path.split("/") if s]
        if len(segments) > 4 and len(segments) != len(set(segments)):
            return False

        # dokuwiki param infinite variants
        if "doku.php" in path:
            return False
        if re.search(r"(do=|rev=|diff|ns=|tab_)", parsed.query.lower()):
            return False
        
        # sort/filter/action parameter traps
        if re.search(r"(sort|order|filter|action)=", parsed.query.lower()):
            return False
        
        # pagination traps
        if re.search(r"(page|p)=\d{3,}", parsed.query.lower()):
            return False

        #fetch/proxy/download traps
        path = parsed.path.lower()
        if "fetch.php" in path or "download" in path or "login.php" in path:
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
    
    except TypeError:
        print ("TypeError for ", parsed)
        raise