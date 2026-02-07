import re
from urllib.parse import urlparse
from urllib.parse import urljoin
from urllib.parse import urldefrag
from bs4 import BeautifulSoup
from utils.response import Response

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
    hyperlinks = set()

    if 600 <= resp.status <= 608:
        print(f"Error: {resp.error}")
        return hyperlinks

    if resp.status != 200:
        print(f"Error: {resp.error}")
        return hyperlinks
    
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    links = soup.find_all("a", href=True)

    for alink in links:
        link = urljoin(resp.url, alink["href"])
        clean_url, fragment = urldefrag(link)
        hyperlinks.add(clean_url)

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
        if re.search(r"/(calendar|date|year|month)/\d{4}", parsed.path):
            return False

        if parsed.query.count("&") > 5:
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
