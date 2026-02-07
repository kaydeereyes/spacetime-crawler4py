import re
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.parse import urldefrag, parse_qsl, urlencode
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

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    global longest_page
    hyperlinks = set()

    if 600 <= resp.status <= 608:
        print(f"Error: {resp.error}")
        return hyperlinks

    if resp.status != 200:
        print(f"Error: {resp.error}")
        return hyperlinks
    
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    
    links = soup.find_all("a", href=True)

        
    page_url, _ = urldefrag(resp.url)
    unique_urls.add(page_url)

    text = soup.get_text(separator=" ")
    tokens = tokenize_text(text)
    filtered = list()

    for word in tokens:
        if word not in STOPWORDS:
            filtered.append(word)

    word_count = len(filtered)

    if word_count > longest_page[1]:
        longest_page = (page_url, word_count)

    for alink in links:
        link = urljoin(resp.url, alink["href"])

        #remove fragments
        clean_url, _ = urldefrag(link)
        parsed = urlparse(link)

        #scheme + host
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()

        # remove default ports
        port = parsed.port
        if port in [80, 443, None]:
            netloc = host
        else:
            netloc = f"{host}:{port}"

        # normalize path
        path = parsed.path.rstrip("/")
        if path == "":
            path = "/"
        
        #sort query parameters
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        query_params.sort()
        query = urlencode(query_params)

        clean_url = f"{scheme}://{netloc}{path}"
        if query:
            clean_url += f"?{query}"

        hyperlinks.add(clean_url)

    return hyperlinks

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        
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
        if re.search(r"\d{4}-\d{2}-\d{2}", parsed.path):
            return False
        if re.search(r"\d{4}/\d{2}/\d{2}", parsed.path):
            return False
        if "tribe__" in parsed.query:
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

        #doku.php trap
        if parsed.query and re.search(r"(do=|tab_|image=|ns=)", parsed.query.lower()):
            return False

        #block infinite page traps
        if re.search(r"/page/\d+", parsed.path.lower()):
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
