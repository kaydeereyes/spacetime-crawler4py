import re
from urllib.parse import urlparse, urljoin, urldefrag, parse_qsl, urlencode, urlunparse
from bs4 import BeautifulSoup
from utils.response import Response

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
    "subject","utm_source","utm_medium","utm_campaign","utm_term","utm_content","view"
}

unique_urls = set()
longest_page = ("", 0) # (url, word_count)

def tokenize_text(text: str):
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
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    global longest_page
    hyperlinks = set()

    if 600 <= resp.status <= 608:
        print(f"Error: {resp.error}")
        return hyperlinks

    if resp.status != 200:
        print(f"Error: {resp.error}")
        return hyperlinks
    
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    
    # Remove script and style elements so only visible page text is processed
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    
    links = soup.find_all("a", href=True)

    # Q1: add the defragmented url to the set of unique urls
    page_url, _ = urldefrag(resp.url)
    unique_urls.add(page_url)

    # Extract text and tokenize for word count
    text = soup.get_text(separator=" ")
    tokens = tokenize_text(text)

    # Filter out stopwords
    filtered = list()
    for word in tokens:
        if word not in STOPWORDS:
            filtered.append(word)

    # Q2: update longest_page if the current page has more words
    word_count = len(filtered)
    if word_count > longest_page[1]:
        longest_page = (page_url, word_count)

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

    return hyperlinks

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

        #DETECT TRAPS
        #calendars
        if re.search(r"/(calendar|date|year|month|archive)/\d{4}", parsed.path.lower()):
            return False

        #infinite queries
        if parsed.query:
            params = parsed.query.split("&")
            if len(params) > 5:
                return False

        #infinite directories
        if parsed.path.count("/") > 10:
            return False

        #infinite param variants
        if re.search(r"(utm_|session|ref|fbclid|gclid)", parsed.query.lower()):
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

# resp_dict = {}
# resp_dict["url"] = "https://ics.uci.edu/~thornton/ics33/Notes/"
# resp_dict["status"] = 200
# resp_dict["response"] = "hello"

# resp = Response(resp_dict)
#scraper("https://ics.uci.edu/~thornton/ics33/Notes/", resp)
