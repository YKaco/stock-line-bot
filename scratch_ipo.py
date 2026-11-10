import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

def test_jpx_or_news():
    q = urllib.parse.quote("新規上場 OR IPO 東証")
    rss_url = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
    req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        xml_data = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall(".//item")[:5]:
            title = item.find("title").text
            pub_date = item.find("pubDate").text
            items.append({"title": title, "date": pub_date})
        for it in items:
            print("-", it["title"], "(", it["date"], ")")
    except Exception as e:
        print("Error RSS:", e)

if __name__ == "__main__":
    test_jpx_or_news()
