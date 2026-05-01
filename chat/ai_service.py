"""
Pure Gemini AI Service - 100% Google Gemini Ecosystem
Phase 5.1: Live Web Search & Perplexity-Style Source Attribution
"""
from django.conf import settings
from .models import Message
import re
import json
import google.generativeai as genai
from ddgs import DDGS
import datetime
import pytz
import trafilatura
import requests
from urllib.parse import urlparse

# URL scraping cache to avoid re-scraping same URLs
_url_scrape_cache = {}

# System instruction enforces Vietnamese and thinking tags protocol
# Phase 5.1: Updated to support web search context and source citations
# Phase 5.7: Enhanced search rules - diversify sources, no support.google, JSON format
# Phase 6.0: Real-Time Web Agent with Notebook LLM integration
SYSTEM_INSTRUCTION = (
    "You are Nova AI, an advanced reasoning assistant with access to live web search and file uploads. "
    "You MUST respond in Vietnamese (Tiếng Việt) unless explicitly asked otherwise. "
    "Before providing your final answer, you MUST meticulously think through the problem. "
    "Enclose your entire thought process within exactly one set of <thinking> and </thinking> tags. "
    "\n\nQUY TẮC TÌM KIẾM VÀ TRÍCH DẪN NGHIÊM NGẶT: "
    "1. ĐA DẠNG HÓA NGUỒN TIN: Tuyệt đối KHÔNG chỉ lấy từ support.google.com hay tài liệu kỹ thuật nội bộ. "
    "2. ƯU TIÊN NGUỒN: Báo lớn (VnExpress, Tuổi Trẻ, Thanh Niên), diễn đàn (Reddit, StackOverflow, Tinhte), blog chuyên gia, trang tin công nghệ uy tín. "
    "3. KỸ THUẬT TÌM KIẾM: Nếu kết quả nghèo nàn, hãy tự động thay đổi query bằng cả tiếng Việt và tiếng Anh. "
    "4. FORMAT TRÍCH DẪN WEB: Mọi nguồn web PHẢI được đặt trong thẻ <sources>[{\"title\": \"...\", \"url\": \"...\"}]</sources> ở ngay ĐẦU câu trả lời. "
    "5. CHỈ DÙNG LINK GỐC: Không dùng link trung gian của Google Search. "
    "6. ƯU TIÊN TIN MỚI: Luôn ưu tiên thông tin mới nhất trong vòng 24 giờ nếu là tin tức thời sự. "
    "\n\nWORKFLOW TÌM KIẾM VÀ ĐỀ XUẤT (Search, Suggest & Confirm): "
    "KHI NGƯỜI DÙNG NHỜ TÌM KIẾM TÀI LIỆU/THÔNG TIN: "
    "- Bước 1: Dùng Google Search Tool để tìm 3-5 links liên quan. "
    "- Bước 2: Tóm tắt ngắn gọn các kết quả tìm được. "
    "- Bước 3: HỎI LẠI NGƯỜI DÙNG: 'Sếp có muốn tôi nạp các link này vào Notebook để phân tích chi tiết không?' "
    "- Bước 4: NẾU NGƯỜI DÙNG ĐỒNG Ý (nói 'có', 'đồng ý', 'nạp', 'import', 'thêm'): "
    "  → Output thẻ ẩn: [IMPORT_URLS: url1, url2, url3, ...] (chỉ 1 lần duy nhất ở cuối) "
    "  → Sau đó mới bắt đầu phân tích chi tiết từ các nguồn đã nạp. "
    "\n\nQUY TẮC TRÍCH DẪN FILE KHI ĐỌC FILE ĐÍNH KÈM: "
    "- Khi người dùng gửi file (PDF, TXT, DOCX, etc.), BẮT BUỘC phải trích dẫn nguồn từ file đó. "
    "- Sử dụng format: [File: tên_file.pdf, trang X] hoặc [File: data.docx, dòng Y-Z] "
    "- Liệt kê các file đã đọc ở đầu phần thinking với format: ĐÃ ĐỌC: tên_file.pdf, data.docx... "
    "- Trong câu trả lời cuối, thêm phần 'Nguồn tài liệu:' liệt kê tất cả file đã tham khảo. "
    "\n\nWhen web search results are provided, analyze them carefully and cite sources using [1], [2], etc. "
    "ĐẶC BIỆT KHI NGƯỜI DÙNG HỎI HOẶC GỬI CODE: "
    "1. BẮT BUỘC phân tích vấn đề, tìm lỗi sai hoặc định hình thuật toán BÊN TRONG thẻ <thinking>. "
    "2. Phần kết quả cuối cùng (BÊN NGOÀI thẻ thinking), chỉ xuất ra đoạn code đã hoàn thiện đặt trong block Markdown (ví dụ: ```python ... ```). "
    "3. Có thể thêm 1-2 dòng giải thích ngắn gọn bên dưới đoạn code. "
    "Do NOT put your final response inside the thinking tags. "
    "Immediately after the closing </thinking> tag, provide your final formatted answer in Vietnamese."
)

def perform_web_search(query, max_results=15):
    """
    Perform web search using DuckDuckGo.
    PHASE 3: Major search improvements - direct keyword matching, Vietnamese support,
    multiple strategies, better relevance scoring.
    Returns list of dicts with title, href, and body - sorted by relevance.
    """
    try:
        # Keep original query exactly as user typed - NO MODIFICATION
        original_query = query.strip()
        print(f"[WEB SEARCH] Original query: '{original_query}' (max_results={max_results})")
        
        with DDGS() as ddgs:
            all_results = []
            seen_urls = set()
            
            # Helper to add result without duplicates
            def add_result(r, source_name):
                href = r.get('href', '')
                if href and href not in seen_urls and len(href) > 10:
                    seen_urls.add(href)
                    all_results.append({
                        'title': r.get('title', ''),
                        'href': href,
                        'body': r.get('body', ''),
                        'source': source_name
                    })
                    return True
                return False
            
            # STRATEGY 1: Direct search with original query (MOST IMPORTANT)
            try:
                results = list(ddgs.text(original_query, max_results=max_results))
                print(f"[WEB SEARCH] Direct search returned {len(results)} results")
                for r in results:
                    add_result(r, 'direct')
            except Exception as e:
                print(f"[WEB SEARCH] Direct search error: {e}")
            
            # STRATEGY 2: Exact phrase search with quotes
            if ' ' in original_query:
                try:
                    quoted_query = f'"{original_query}"'
                    quoted_results = list(ddgs.text(quoted_query, max_results=8))
                    print(f"[WEB SEARCH] Exact phrase search returned {len(quoted_results)} results")
                    for r in quoted_results:
                        add_result(r, 'exact_phrase')
                except Exception as e:
                    print(f"[WEB SEARCH] Exact phrase error: {e}")
            
            # STRATEGY 3: Search without common words (for longer queries)
            words = original_query.split()
            if len(words) > 3:
                # Remove common words and search with just keywords
                common_words = {'là', 'của', 'và', 'các', 'các', 'những', 'để', 'có', 'được', 
                               'trong', 'với', 'cho', 'về', 'the', 'a', 'an', 'is', 'are', 
                               'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                               'do', 'does', 'did', 'will', 'would', 'could', 'should'}
                important_words = [w for w in words if w.lower() not in common_words and len(w) > 2]
                if len(important_words) >= 2:
                    keyword_query = ' '.join(important_words[:6])  # Max 6 keywords
                    try:
                        keyword_results = list(ddgs.text(keyword_query, max_results=6))
                        print(f"[WEB SEARCH] Keyword search '{keyword_query}' returned {len(keyword_results)} results")
                        for r in keyword_results:
                            add_result(r, 'keywords')
                    except Exception as e:
                        print(f"[WEB SEARCH] Keyword search error: {e}")
            
            # STRATEGY 4: Vietnamese-specific modifications
            # Replace English tech terms with common alternatives
            vi_modifications = {
                'python': 'python lập trình',
                'javascript': 'javascript js lập trình',
                'tutorial': 'hướng dẫn tutorial',
                'learning': 'học learning',
                'programming': 'lập trình programming',
            }
            
            vi_query = original_query
            for en, vi in vi_modifications.items():
                if en in original_query.lower():
                    vi_query = vi_query.replace(en, vi)
            
            if vi_query != original_query:
                try:
                    vi_results = list(ddgs.text(vi_query, max_results=6))
                    print(f"[WEB SEARCH] VI-modified search returned {len(vi_results)} results")
                    for r in vi_results:
                        add_result(r, 'vi_modified')
                except Exception as e:
                    print(f"[WEB SEARCH] VI search error: {e}")
            
            # STRATEGY 5: Site-specific search for common domains
            if len(all_results) < 5:
                # Try adding site: modifiers for popular Vietnamese/tech sites
                popular_sites = ['viblo.asia', 'stackoverflow.com', 'github.com', 'medium.com']
                for site in popular_sites[:2]:  # Limit to avoid too many requests
                    site_query = f'{original_query} site:{site}'
                    try:
                        site_results = list(ddgs.text(site_query, max_results=3))
                        print(f"[WEB SEARCH] Site search '{site}' returned {len(site_results)} results")
                        for r in site_results:
                            add_result(r, f'site_{site}')
                    except Exception as e:
                        print(f"[WEB SEARCH] Site search error: {e}")
            
            print(f"[WEB SEARCH] Total unique results: {len(all_results)}")
            
            # ENHANCED RELEVANCE SCORING
            query_lower = original_query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]
            
            scored_results = []
            for r in all_results:
                score = 0
                title_lower = r['title'].lower()
                body_lower = r['body'].lower()
                url_lower = r['href'].lower()
                
                # EXACT MATCHES (highest priority)
                if query_lower == title_lower:
                    score += 100  # Perfect title match
                elif query_lower in title_lower:
                    score += 50   # Query in title
                
                if query_lower in body_lower:
                    score += 30   # Query in body
                
                # WORD-BY-WORD MATCHING
                for word in query_words:
                    if word in title_lower:
                        score += 10  # Each word in title
                    if word in body_lower:
                        score += 3   # Each word in body
                    # Count occurrences
                    score += body_lower.count(word)
                
                # URL MATCHES (domain relevance)
                for word in query_words:
                    if word in url_lower:
                        score += 5
                
                # SOURCE BOOSTS
                source = r.get('source', 'direct')
                if source == 'exact_phrase':
                    score += 25  # Big boost for exact phrase
                elif source == 'direct':
                    score += 15  # Boost for direct match
                elif source.startswith('site_'):
                    score += 10  # Small boost for site-specific
                
                # QUALITY PENALTIES
                if len(r['body']) < 30:
                    score -= 20  # Very short description
                elif len(r['body']) < 80:
                    score -= 10  # Short description
                
                # Domain quality boosts
                quality_domains = ['github.com', 'stackoverflow.com', 'medium.com', 
                                  'viblo.asia', 'dev.to', 'docs.', 'documentation']
                for domain in quality_domains:
                    if domain in url_lower:
                        score += 8
                        break
                
                # Penalize spam domains
                spam_domains = ['click', 'ads', 'tracking', 'short.link']
                for spam in spam_domains:
                    if spam in url_lower:
                        score -= 30
                        break
                
                # Store score for sorting
                r['score'] = score
                scored_results.append(r)
            
            # Sort by score descending
            scored_results.sort(key=lambda x: x['score'], reverse=True)
            
            # Log top scores before removing
            top_scores = [r.get('score', 0) for r in scored_results[:5]]
            print(f"[WEB SEARCH] Found {len(scored_results)} results, top scores: {top_scores}")
            
            # Remove score field before returning
            for r in scored_results:
                r.pop('score', None)
                r.pop('source', None)
            return scored_results
            
    except Exception as e:
        print(f"[ERROR] Web search failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def scrape_with_selenium(url, max_length=200000, wait_time=15, capture_screenshot=True, preserve_formatting=True):
    """
    Scrape content using Selenium for JavaScript-heavy websites.
    PHASE 3: Deep scraping with auto-click 'load more', screenshot capture, and structured formatting.
    
    IMPORTANT: Selenium runs in HEADLESS mode (chạy NGẦM, không hiện cửa sổ browser):
    - --headless=new flag makes it run invisibly in background
    - No browser window will appear during scraping
    - This is server-friendly and faster
    
    Features:
    - Auto-clicks 'read more', 'load more', 'see more' buttons
    - Multiple scroll cycles with waiting
    - SCREENSHOT CAPTURE: Takes full page screenshot
    - STRUCTURED FORMATTING: Preserves headings, paragraphs, lists
    - Extracts related links for further crawling
    - Longer waits for dynamic content
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    from bs4 import BeautifulSoup, NavigableString
    import time
    import re
    import base64
    from urllib.parse import urlparse, urljoin

    print(f"[SELENIUM PHASE 3] Starting deep scrape for {url}")
    print(f"[SELENIUM] max_length={max_length}, wait={wait_time}s, screenshot={capture_screenshot}")
    print(f"[SELENIUM] NOTE: Running in HEADLESS mode (chạy ngầm, không hiện browser)")

    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    # DO NOT disable JavaScript - we need it for clicking buttons
    chrome_options.add_argument('--disable-extensions')

    driver = None
    all_html_snapshots = []  # Store multiple snapshots
    extracted_links = []     # Store related links
    screenshot_base64 = None # Store screenshot
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })
        
        # Set initial viewport for consistent screenshots
        driver.set_window_size(1920, 1080)

        print(f"[SELENIUM] Loading {url}...")
        driver.get(url)

        # Initial wait for page load
        print(f"[SELENIUM] Initial wait: {wait_time}s...")
        time.sleep(wait_time)
        
        # PHASE 1: Multiple scroll cycles (more aggressive)
        print("[SELENIUM] Phase 1: Deep scrolling (3 cycles)...")
        for cycle in range(3):
            print(f"[SELENIUM] Scroll cycle {cycle + 1}/3")
            # Scroll progressively
            for scroll_pct in [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
                driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {scroll_pct});")
                time.sleep(2)  # Wait for lazy loading
            
            # Wait between cycles
            time.sleep(3)
            
            # Capture HTML snapshot
            snapshot = driver.page_source
            all_html_snapshots.append(snapshot)
            print(f"[SELENIUM] Snapshot {cycle + 1}: {len(snapshot)} chars")
        
        # PHASE 2: Auto-click "Load More" / "Read More" / "See More" buttons
        print("[SELENIUM] Phase 2: Looking for 'load more' buttons...")
        load_more_selectors = [
            # Vietnamese
            "button:contains('Xem thêm')", "button:contains('Đọc thêm')", "button:contains('Tải thêm')",
            "a:contains('Xem thêm')", "a:contains('Đọc thêm')", "a:contains('Tải thêm')",
            "*[class*='xem-them']", "*[class*='doc-them']", "*[class*='load-more']",
            # English
            "button:contains('Load more')", "button:contains('Read more')", "button:contains('Show more')",
            "button:contains('See more')", "button:contains('View more')",
            "a:contains('Load more')", "a:contains('Read more')", "a:contains('Show more')",
            "*[class*='load-more']", "*[class*='read-more']", "*[class*='show-more']",
            "*[class*='view-more']", "*[class*='expand']", "*[class*='pagination']",
            # Common class names
            ".load-more", ".read-more", ".show-more", ".view-more", ".expand-content",
            "[data-action='load-more']", "[data-action='expand']",
            "button[class*='more']", "a[class*='more']",
            # Next page
            "a:contains('Next')", "a:contains('→')", ".next", "[rel='next']"
        ]
        
        clicked_count = 0
        max_clicks = 5  # Limit to prevent infinite loops
        
        for attempt in range(max_clicks):
            found_button = False
            
            # Try different button finding strategies
            strategies = [
                # Strategy 1: By text content (JavaScript) - EXPANDED KEYWORDS
                lambda: driver.execute_script("""
                    var buttons = document.querySelectorAll('button, a, [role="button"], .btn, [class*="button"]');
                    var keywords = ['xem thêm', 'đọc thêm', 'tải thêm', 'xem tiếp', 'đọc tiếp', 'hiển thị thêm',
                                   'load more', 'read more', 'show more', 'see more', 'view more', 'expand',
                                   'more', 'tiếp tục', 'continue', 'mở rộng', 'unfold',
                                   'older posts', 'bài cũ hơn', 'next page', 'trang sau',
                                   'view all', 'xem tất cả', 'show all', 'hiện tất cả',
                                   'load comments', 'tải bình luận', 'more comments', 'replies', 'trả lời'];
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].textContent.toLowerCase().trim();
                        var ariaLabel = (buttons[i].getAttribute('aria-label') || '').toLowerCase();
                        var title = (buttons[i].getAttribute('title') || '').toLowerCase();
                        for (var k = 0; k < keywords.length; k++) {
                            if (text.includes(keywords[k]) || ariaLabel.includes(keywords[k]) || title.includes(keywords[k])) {
                                var rect = buttons[i].getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) return buttons[i];
                            }
                        }
                    }
                    return null;
                """),
                # Strategy 2: By class names - EXPANDED SELECTORS
                lambda: driver.execute_script("""
                    var selectors = ['.load-more', '.read-more', '.show-more', '.view-more', 
                                     '.xem-them', '.doc-them', '.xem-tiep', '.hien-thi-them',
                                     '.expand-content', '.expandable', '.collapsed',
                                     '[class*="load"]', '[class*="more"]', '[class*="expand"]', 
                                     '[class*="pagination"]', '.btn-more', '.btn-expand',
                                     '.see-all', '.view-all', '.show-all', '.infinite-scroll'];
                    for (var s = 0; s < selectors.length; s++) {
                        var elements = document.querySelectorAll(selectors[s]);
                        for (var e = 0; e < elements.length; e++) {
                            if (elements[e].offsetParent !== null) return elements[e];
                        }
                    }
                    return null;
                """),
                # Strategy 3: Pagination next - EXPANDED
                lambda: driver.execute_script("""
                    var selectors = ['.next', '.pagination .next', '.page-next', 
                                     '[rel="next"]', 'a[href*="page"]', 'a[href*="/p/"]',
                                     'button[aria-label*="next"]', '.older-posts', 
                                     '.nav-previous', '.pagination-link'];
                    for (var s = 0; s < selectors.length; s++) {
                        var elements = document.querySelectorAll(selectors[s]);
                        for (var e = 0; e < elements.length; e++) {
                            var el = elements[e];
                            if (el.offsetParent !== null && !el.disabled) return el;
                        }
                    }
                    return null;
                """),
                # Strategy 4: Accordion/Expandable sections
                lambda: driver.execute_script("""
                    var accordions = document.querySelectorAll('[data-toggle="collapse"], [data-bs-toggle="collapse"], .accordion-button');
                    for (var i = 0; i < accordions.length; i++) {
                        var acc = accordions[i];
                        var isExpanded = acc.getAttribute('aria-expanded') === 'true';
                        if (!isExpanded && acc.offsetParent !== null) return acc;
                    }
                    return null;
                """)
            ]
            
            for strategy in strategies:
                try:
                    button = strategy()
                    if button:
                        print(f"[SELENIUM] Found button to click (attempt {attempt + 1})")
                        # Scroll to button
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                        time.sleep(1)
                        
                        # Try to click
                        try:
                            button.click()
                            clicked_count += 1
                            found_button = True
                            print(f"[SELENIUM] Clicked button #{clicked_count}, waiting for content...")
                            time.sleep(5)  # Wait for new content to load
                            
                            # Scroll to load new lazy content
                            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(3)
                            
                            # Capture new snapshot
                            new_snapshot = driver.page_source
                            if len(new_snapshot) > len(all_html_snapshots[-1]) * 1.1:  # 10% more content
                                all_html_snapshots.append(new_snapshot)
                                print(f"[SELENIUM] New content loaded! Total: {len(all_html_snapshots)} snapshots")
                            break
                        except Exception as click_err:
                            print(f"[SELENIUM] Click failed: {click_err}")
                            continue
                except Exception as strat_err:
                    continue
            
            if not found_button:
                print("[SELENIUM] No more buttons found to click")
                break
        
        print(f"[SELENIUM] Total buttons clicked: {clicked_count}")
        
        # PHASE 3: Extract related links
        print("[SELENIUM] Phase 3: Extracting related links...")
        try:
            links_data = driver.execute_script("""
                var links = [];
                var allLinks = document.querySelectorAll('a[href]');
                var baseUrl = window.location.origin;
                var currentPath = window.location.pathname;
                
                for (var i = 0; i < allLinks.length && links.length < 20; i++) {
                    var link = allLinks[i];
                    var href = link.getAttribute('href');
                    var text = link.textContent.trim();
                    
                    if (!href || href.startsWith('#') || href.startsWith('javascript:')) continue;
                    if (href.startsWith('mailto:') || href.startsWith('tel:')) continue;
                    
                    // Make absolute URL
                    if (href.startsWith('/')) {
                        href = baseUrl + href;
                    } else if (!href.startsWith('http')) {
                        href = baseUrl + '/' + href;
                    }
                    
                    // Skip external links
                    if (!href.includes(window.location.hostname)) continue;
                    
                    // Skip current page
                    if (href === window.location.href) continue;
                    
                    // Check if text looks like article/content link
                    var isContentLink = text.length > 10 && text.length < 200;
                    var hasContentWords = /(bài viết|article|blog|post|doc|tài liệu|hướng dẫn|guide|tutorial)/i.test(text);
                    var isRelevant = isContentLink || hasContentWords;
                    
                    if (isRelevant || text.length > 20) {
                        links.push({
                            url: href,
                            text: text.substring(0, 100),
                            isContent: isRelevant
                        });
                    }
                }
                return links;
            """)
            
            if links_data:
                extracted_links = links_data
                print(f"[SELENIUM] Found {len(extracted_links)} related links")
                for link in extracted_links[:5]:
                    print(f"  - {link['text'][:50]}... ({link['url'][:60]})")
        except Exception as link_err:
            print(f"[SELENIUM] Link extraction error: {link_err}")
        
        # PHASE 4: MERGE ALL SNAPSHOTS - get maximum content
        print("[SELENIUM] Phase 4: MERGING ALL SNAPSHOTS for maximum content...")
        
        # Instead of just using largest, MERGE all unique content from all snapshots
        merged_soup = None
        all_unique_texts = []
        all_seen_hashes = set()
        
        def content_hash(text):
            """Simple hash for deduplication"""
            import hashlib
            return hashlib.md5(text[:500].encode()).hexdigest()[:16]
        
        for i, snapshot in enumerate(all_html_snapshots):
            soup_temp = BeautifulSoup(snapshot, 'html.parser')
            # Remove unwanted but KEEP scripts for JSON extraction
            for tag in soup_temp(['nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            text = soup_temp.get_text(separator='\n', strip=True)
            text_hash = content_hash(text)
            
            if text_hash not in all_seen_hashes:
                all_seen_hashes.add(text_hash)
                all_unique_texts.append(text)
                print(f"[SELENIUM] Snapshot {i+1}: {len(text)} chars (NEW)")
                
                # Use first snapshot as base for merged soup
                if merged_soup is None:
                    merged_soup = soup_temp
            else:
                print(f"[SELENIUM] Snapshot {i+1}: {len(text)} chars (DUPLICATE)")
        
        # Use merged soup or fall back to largest
        if merged_soup:
            final_soup = merged_soup
            print(f"[SELENIUM] Using merged soup with {len(all_unique_texts)} unique content chunks")
        else:
            final_soup = BeautifulSoup(max(all_html_snapshots, key=len), 'html.parser')
            print(f"[SELENIUM] Using largest snapshot: {len(str(final_soup))} chars")
        
        # PHASE 5: CAPTURE SCREENSHOT before quitting
        if capture_screenshot:
            print("[SELENIUM] Phase 5: Capturing screenshot...")
            try:
                # Scroll to top first for consistent screenshot
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                
                # Capture screenshot as base64
                screenshot_png = driver.get_screenshot_as_png()
                screenshot_base64 = base64.b64encode(screenshot_png).decode('utf-8')
                print(f"[SELENIUM] Screenshot captured: {len(screenshot_base64)} chars (base64)")
            except Exception as ss_err:
                print(f"[SELENIUM] Screenshot capture failed: {ss_err}")
        
        driver.quit()

        # Use merged soup for parsing
        print(f"[SELENIUM] Parsing merged content...")
        
        # Work with merged soup
        soup = final_soup
        
        # EXTRACT JSON DATA from scripts BEFORE removing them
        json_data_found = []
        for script in soup.find_all('script', type='application/json'):
            try:
                import json
                json_text = script.string
                if json_text and len(json_text) > 100:
                    data = json.loads(json_text)
                    # Try to extract readable content from JSON
                    if isinstance(data, dict):
                        # Common patterns: article data, product data, etc.
                        for key in ['article', 'post', 'product', 'content', 'data']:
                            if key in data and isinstance(data[key], dict):
                                json_content = str(data[key])
                                if len(json_content) > 200:
                                    json_data_found.append(f"[JSON DATA: {key}]\n{json_content[:2000]}")
                    elif isinstance(data, list) and len(data) > 0:
                        json_data_found.append(f"[JSON ARRAY: {len(data)} items]\n{str(data)[:2000]}")
            except:
                pass
        
        if json_data_found:
            print(f"[SELENIUM] Found {len(json_data_found)} JSON data blocks")
        
        # EXTRACT IFRAME content info (before removing)
        iframe_info = []
        for iframe in soup.find_all('iframe', src=True):
            src = iframe.get('src', '')
            if src:
                iframe_info.append(f"[IFRAME: {src[:100]}]")
        
        # NOW remove unwanted elements (keep iframes info but remove tags)
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'advertisement', '.ad', '.ads', '.sidebar', '.comment', '.comments']):
            tag.decompose()

        # Try to get title - MULTIPLE SOURCES
        title = url
        title_sources = []
        
        # 1. From title tag
        if soup.find('title'):
            title_sources.append(soup.find('title').get_text(strip=True))
        
        # 2. From h1
        h1 = soup.find('h1')
        if h1:
            title_sources.append(h1.get_text(strip=True))
        
        # 3. From meta title
        meta_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'twitter:title'})
        if meta_title:
            title_sources.append(meta_title.get('content', ''))
        
        # Use longest title (usually most descriptive)
        if title_sources:
            title = max(title_sources, key=len)
        
        # EXTRACT META DATA
        meta_data = {}
        meta_selectors = [
            ('description', 'meta[name="description"]', 'content'),
            ('og_desc', 'meta[property="og:description"]', 'content'),
            ('keywords', 'meta[name="keywords"]', 'content'),
            ('author', 'meta[name="author"]', 'content'),
            ('published', 'meta[property="article:published_time"]', 'content'),
            ('modified', 'meta[property="article:modified_time"]', 'content'),
        ]
        for key, selector, attr in meta_selectors:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                meta_data[key] = tag.get(attr)

        # Extract content with PRESERVED FORMATTING
        # PHASE 3: Better text extraction to prevent word concatenation
        def extract_structured_text(element, depth=0):
            """
            Extract text while preserving structure (headings, paragraphs, lists).
            This prevents words from being concatenated together.
            """
            if not element:
                return ""
            
            text_parts = []
            
            # Handle different element types
            if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = element.get_text(strip=True)
                if text:
                    level = element.name[1]
                    text_parts.append(f"\n{'#' * int(level)} {text}\n")
                    
            elif element.name == 'p':
                text = element.get_text(strip=True)
                if text and len(text) > 5:
                    text_parts.append(f"{text}\n")
                    
            elif element.name in ['ul', 'ol']:
                items = element.find_all('li', recursive=False)
                for i, li in enumerate(items, 1):
                    li_text = li.get_text(strip=True)
                    if li_text:
                        prefix = "• " if element.name == 'ul' else f"{i}. "
                        text_parts.append(f"{prefix}{li_text}\n")
                text_parts.append("\n")
                
            elif element.name == 'blockquote':
                text = element.get_text(strip=True)
                if text:
                    lines = text.split('\n')
                    quoted = '\n'.join(f"> {line}" for line in lines)
                    text_parts.append(f"\n{quoted}\n\n")
                    
            elif element.name == 'pre' or element.name == 'code':
                text = element.get_text(strip=True)
                if text and len(text) > 10:
                    text_parts.append(f"\n```\n{text}\n```\n")
            
            elif element.name == 'table':
                # Extract table with structure
                rows = []
                header_rows = element.find_all('thead')
                body_rows = element.find_all('tbody')
                
                # Get headers
                headers = []
                for thead in header_rows:
                    ths = thead.find_all('th')
                    headers = [th.get_text(strip=True) for th in ths]
                
                # If no thead, try first row
                if not headers:
                    first_row = element.find('tr')
                    if first_row:
                        ths = first_row.find_all(['th', 'td'])
                        headers = [th.get_text(strip=True) for th in ths]
                
                # Get all data rows
                all_rows = element.find_all('tr')
                table_text = ["\n[TABLE START]"]
                
                for i, row in enumerate(all_rows[:50]):  # Limit to 50 rows
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        row_text = " | ".join(cell.get_text(strip=True) for cell in cells)
                        if row_text.strip():
                            table_text.append(row_text)
                
                table_text.append("[TABLE END]\n")
                text_parts.append("\n".join(table_text))
                    
            elif element.name in ['div', 'section', 'article', 'main']:
                # Process children recursively with proper spacing
                for child in element.children:
                    if hasattr(child, 'name') and child.name:
                        child_text = extract_structured_text(child, depth + 1)
                        if child_text:
                            text_parts.append(child_text)
                            # Add space after block elements for proper separation
                            if child.name in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'pre', 'table']:
                                text_parts.append('\n')
                    elif isinstance(child, NavigableString):
                        text = str(child).strip()
                        # Lower threshold to catch more inline text
                        if text and len(text) > 3:
                            text_parts.append(text)
                            text_parts.append(' ')  # Add space after inline text
                            
            # Join with spaces, then clean up extra spaces
            result = ' '.join(text_parts)
            # Clean up multiple spaces but keep newlines
            import re
            result = re.sub(r' +', ' ', result)  # Multiple spaces -> single space
            result = re.sub(r' \n', '\n', result)  # Space before newline -> just newline
            result = re.sub(r'\n ', '\n', result)  # Space after newline -> just newline
            return result
        
        # Try multiple selectors in priority order
        content_parts = []
        selectors = [
            'main', 'article', '[role="main"]',
            '.content', '.post-content', '.entry-content', '.article-content',
            '#content', '#main-content', '.main',
            '.post', '.blog-post', '.page-content',
            'section.content', 'div[role="main"]',
            '[data-testid]', '.prose', '.markdown-body',
            '.docs-content', '.documentation', '.readme',
            '.container article', '.wrapper article'
        ]

        print(f"[SELENIUM] Trying {len(selectors)} selectors with structured extraction...")
        found_content = False

        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                print(f"[SELENIUM] Found {len(elements)} elements with selector: {selector}")
                for element in elements:
                    # Use structured extraction instead of simple get_text
                    structured_text = extract_structured_text(element)
                    text_length = len(structured_text)
                    if text_length > 100:
                        print(f"[SELENIUM] Selector '{selector}' gave {text_length} chars (structured)")
                        if structured_text not in content_parts:
                            content_parts.append(structured_text)
                            found_content = True
                            if len('\n\n'.join(content_parts)) > max_length:
                                break
                if found_content and len('\n\n'.join(content_parts)) > 2000:
                    break

        # If still not enough or no content found, try body as fallback
        total_content = '\n\n'.join(content_parts)
        if not found_content or len(total_content) < 1000:
            print(f"[SELENIUM] Selectors only gave {len(total_content)} chars, trying structured body extraction...")
            body = soup.find('body')
            if body:
                # Use structured extraction on body
                body_text = extract_structured_text(body)
                print(f"[SELENIUM] Structured body extraction gave {len(body_text)} chars")
                if len(body_text) > len(total_content):
                    content_parts = [body_text]
                elif len(body_text) > 200:
                    content_parts.append(body_text)

        # If still insufficient, try getting all visible text
        total_content = '\n\n'.join(content_parts)
        if len(total_content) < 500:
            print(f"[SELENIUM] Still only {len(total_content)} chars, extracting all visible text...")
            all_text = soup.get_text(separator='\n', strip=True)
            print(f"[SELENIUM] All text extraction: {len(all_text)} chars")
            if len(all_text) > len(total_content):
                content_parts = [all_text]

        # Combine all content
        content = '\n\n'.join(content_parts)

        # Extract images with captions
        images = []
        try:
            # Find all images in the article/content area
            img_selectors = ['article img', 'main img', '.content img', '.post-content img', 'figure img', '.thumb img', 'img[src]']
            seen_urls = set()

            for selector in img_selectors:
                for img in soup.select(selector):
                    src = img.get('src', '')
                    if not src or src in seen_urls:
                        continue

                    # Make absolute URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        from urllib.parse import urlparse
                        parsed = urlparse(url)
                        src = f"{parsed.scheme}://{parsed.netloc}{src}"

                    # Skip small icons, tracking pixels
                    if 'icon' in src.lower() or 'pixel' in src.lower() or 'gif' in src.lower():
                        continue

                    seen_urls.add(src)

                    # Get caption
                    caption = ''
                    figcaption = img.find_parent('figure')
                    if figcaption:
                        caption_elem = figcaption.find('figcaption')
                        if caption_elem:
                            caption = caption_elem.get_text(strip=True)

                    if not caption:
                        # Try alt text
                        caption = img.get('alt', '')

                    if len(images) < 10:  # Limit to 10 images
                        images.append({
                            'url': src,
                            'caption': caption[:200]
                        })

            if images:
                print(f"[SELENIUM] Found {len(images)} images")
                # Add image references to content
                img_section = "\n\n[IMAGES FOUND]\n"
                for i, img in enumerate(images, 1):
                    img_section += f"\nImage {i}: {img['url']}"
                    if img['caption']:
                        img_section += f"\nCaption: {img['caption']}"
                    img_section += "\n"
                content += img_section

        except Exception as e:
            print(f"[SELENIUM] Error extracting images: {e}")

        # ADD JSON DATA to content if found
        if json_data_found:
            json_section = "\n\n[EMBEDDED JSON DATA]\n" + "\n---\n".join(json_data_found)
            content += json_section
            print(f"[SELENIUM] Added {len(json_section)} chars of JSON data")
        
        # ADD IFRAME INFO to content
        if iframe_info:
            iframe_section = "\n\n[EMBEDDED CONTENT (IFRAMES)]\n" + "\n".join(iframe_info)
            content += iframe_section
        
        # ADD META DATA to content
        if meta_data:
            meta_section = "\n\n[PAGE METADATA]\n"
            for key, value in meta_data.items():
                if value:
                    meta_section += f"{key}: {value}\n"
            content = meta_section + "\n" + content
            print(f"[SELENIUM] Added metadata: {list(meta_data.keys())}")
        
        # ADD ALL UNIQUE TEXTS FROM SNAPSHOTS (merged content)
        if len(all_unique_texts) > 1:
            # Find content that's in later snapshots but not in the main content
            additional_content = []
            for text in all_unique_texts[1:]:  # Skip first (already in main)
                if len(text) > 500 and text[:200] not in content:
                    additional_content.append(text[:5000])  # Add up to 5k chars each
            
            if additional_content:
                extra_section = "\n\n[ADDITIONAL CONTENT FROM DYNAMIC LOADING]\n" + "\n\n---\n\n".join(additional_content)
                content += extra_section
                print(f"[SELENIUM] Added {len(additional_content)} extra content chunks from snapshots")
        
        # Clean up - preserve formatting but remove excessive whitespace
        import re
        content = re.sub(r'\n{5,}', '\n\n\n\n', content)  # Keep some paragraph breaks
        # Normalize spaces but NOT collapse single spaces between words
        content = re.sub(r'[ \t]{2,}', ' ', content)  # Multiple spaces/tabs -> single space (but keep at least 1)
        content = re.sub(r' ([.,;:!?])', r'\1', content)  # Fix spaces before punctuation
        # Ensure there's space between letters that got stuck (e.g., "Helloworld" -> "Hello world")
        # This fixes cases where inline elements didn't have spaces between them
        content = re.sub(r'([a-zA-Z])([A-Z])', r'\1 \2', content)  # camelCase separation
        content = re.sub(r'([a-z]{3,})([A-Z][a-z]{2,})', r'\1 \2', content)  # wordWord separation

        final_length = len(content)
        print(f"[SELENIUM] Extracted {final_length} chars from {url}")

        if final_length < 100:
            print(f"[SELENIUM] WARNING: Very short content ({final_length} chars). Site may block scraping.")

        # Truncate screenshot if too large (max ~500KB of base64)
        screenshot_data = None
        if screenshot_base64 and len(screenshot_base64) < 700000:  # ~500KB limit
            screenshot_data = screenshot_base64
            print(f"[SELENIUM] Including screenshot: {len(screenshot_data)} chars base64")
        elif screenshot_base64:
            print(f"[SELENIUM] Screenshot too large ({len(screenshot_base64)} chars), skipping")

        return {
            'title': title,
            'content': content[:max_length],
            'images': images,
            'success': final_length > 100,
            'source': 'selenium-deep-v2',
            'length': final_length,
            'extracted_links': extracted_links,  # Links to related content
            'snapshots': len(all_html_snapshots),
            'buttons_clicked': clicked_count,
            'screenshot_base64': screenshot_data,  # PNG screenshot as base64
            'has_screenshot': screenshot_data is not None,
            'meta_data': meta_data,  # Page metadata
            'json_data_count': len(json_data_found),  # Number of JSON blocks found
            'iframe_count': len(iframe_info),  # Number of iframes detected
            'unique_snapshots': len(all_unique_texts)  # How many unique content snapshots
        }

    except Exception as e:
        print(f"[SELENIUM] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return {'title': url, 'content': '', 'success': False, 'error': str(e), 'extracted_links': []}


def scrape_url_content(url, max_length=200000):
    """
    Scrape comprehensive content from a URL using multiple methods.
    PHASE 2: Enhanced extraction - deeper scraping, more content, longer waits.
    1. First: requests + trafilatura + BeautifulSoup (extended selectors)
    2. Second (if needed): Selenium for JS-heavy sites (longer wait, more scrolls)
    3. Extract: links, tables, code blocks, images metadata
    Returns dict with title, content, and metadata.
    Uses caching to avoid re-scraping.
    """
    global _url_scrape_cache

    # Check cache first
    if url in _url_scrape_cache:
        print(f"[URL SCRAPE] Cache hit for {url}")
        return _url_scrape_cache[url]

    try:
        print(f"[URL SCRAPE] Phase 1: HTTP fetch for {url}")

        # Fetch with timeout and headers - mimic real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.google.com/'
        }
        
        # Use session to handle cookies
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=45, allow_redirects=True)
        
        # Handle 403 specifically
        if response.status_code == 403:
            print(f"[URL SCRAPE] 403 Forbidden - website blocks scrapers: {url}")
            return {
                'url': url,
                'title': url,
                'content': f"Website {url} đang chặn truy cập tự động (403 Forbidden).\n\nGợi ý:\n- Thử tìm kiếm thông tin từ nguồn khác\n- Hoặc copy-paste nội dung trực tiếp vào chat\n- Một số website như Glints, LinkedIn có cơ chế chống bot nghiêm ngặt",
                'success': False,
                'error': '403 Forbidden - Website blocks automated access'
            }
        
        response.raise_for_status()

        # Extract content with trafilatura - enhanced settings
        downloaded = response.text

        # Try multiple extraction strategies
        content_parts = []

        # 1. Main extraction with all content types
        main_content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_formatting=True,
            deduplicate=True,
            target_language='vi' if 'viblo' in url or 'vn' in url else None
        )
        if main_content and len(main_content.strip()) > 100:
            content_parts.append(main_content)
            print(f"[URL SCRAPE] Trafilatura main: {len(main_content)} chars")

        # 2. Enhanced BeautifulSoup extraction with more selectors
        if not content_parts or len(''.join(content_parts).strip()) < 1000:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(downloaded, 'html.parser')

                # Remove unwanted elements
                for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'advertisement', '.ad', '.ads', '.sidebar', '.comment', '.comments']):
                    tag.decompose()

                # Extended selectors list
                selectors = [
                    'main', 'article', '[role="main"]',
                    '.content', '.post-content', '.entry-content', '.article-content',
                    '#content', '#main-content', '.main',
                    '.post', '.blog-post', '.page-content',
                    'section.content', 'div[role="main"]',
                    '[data-testid]', '.prose', '.markdown-body',
                    '.docs-content', '.documentation', '.readme',
                    '.container article', '.wrapper article',
                    '#article-content', '.story-body', '.article__body'
                ]
                
                main_content_html = None
                best_selector = None
                max_content_length = 0
                
                for selector in selectors:
                    elements = soup.select(selector)
                    for element in elements:
                        # Use space separator to prevent words sticking together
                        text = element.get_text(separator=' ', strip=True)
                        if len(text) > max_content_length:
                            max_content_length = len(text)
                            main_content_html = text
                            best_selector = selector

                # Fallback to body
                if not main_content_html or len(main_content_html) < 500:
                    body = soup.find('body')
                    if body:
                        # Get all meaningful text elements with proper spacing
                        paragraphs = body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'blockquote', 'pre', 'code'])
                        body_text_parts = []
                        for p in paragraphs:
                            # Use separator=' ' to ensure words don't stick together
                            text = p.get_text(separator=' ', strip=True)
                            if len(text) > 15:
                                body_text_parts.append(text)
                        main_content_html = '\n\n'.join(body_text_parts)

                if main_content_html and len(main_content_html.strip()) > 200:
                    main_content_html = re.sub(r'\n{3,}', '\n\n', main_content_html)
                    # Don't truncate here - keep full content
                    content_parts.append("\n\n[CONTENT FROM BEAUTIFULSOUP]\n" + main_content_html)
                    print(f"[URL SCRAPE] BeautifulSoup ({best_selector or 'body'}): {len(main_content_html)} chars")
                    
                # Extract all links from the page
                links = []
                for a in soup.find_all('a', href=True):
                    href = a.get('href', '')
                    text = a.get_text(strip=True)
                    if href and not href.startswith('#') and text and len(text) > 3:
                        # Make absolute URL
                        if href.startswith('//'):
                            href = 'https:' + href
                        elif href.startswith('/'):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            href = f"{parsed.scheme}://{parsed.netloc}{href}"
                        links.append({'url': href, 'text': text[:100]})
                
                if links:
                    print(f"[URL SCRAPE] Found {len(links)} links on page")
                    
            except Exception as e:
                print(f"[URL SCRAPE] BeautifulSoup fallback failed: {e}")

        # 3. Extract metadata
        from trafilatura.metadata import extract_metadata
        metadata = extract_metadata(downloaded)
        title = metadata.title if metadata and metadata.title else url
        author = metadata.author if metadata and metadata.author else None
        date = metadata.date if metadata and metadata.date else None

        # If no title from metadata, try BeautifulSoup
        if title == url:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(downloaded, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True)
                h1_tag = soup.find('h1')
                if h1_tag:
                    title = h1_tag.get_text(strip=True)
            except:
                pass

        # Combine all content
        full_content = '\n\n'.join(filter(None, content_parts))
        print(f"[URL SCRAPE] Phase 1 content length: {len(full_content)} chars")

        # PHASE 2: Deep scraping với Selenium cho tất cả URL (không chỉ JS-heavy)
        # PHASE 3: Luôn dùng Selenium để có thể click "đọc thêm" và extract links
        js_heavy_sites = ['viblo.asia', 'facebook.com', 'twitter.com', 'x.com', 'linkedin.com', 'medium.com', 'dev.to', 'substack.com']
        is_js_heavy = any(site in url.lower() for site in js_heavy_sites)
        
        extracted_links = links if 'links' in dir() else []
        selenium_buttons_clicked = 0
        selenium_snapshots = 0

        # PHASE 3: Use enhanced Selenium scraping for ALL URLs to get maximum content
        if len(full_content.strip()) < 3000 or is_js_heavy or True:  # Force Selenium for all
            print(f"[URL SCRAPE] Phase 2: Deep scraping với Selenium...")
            try:
                # PHASE 3: Longer wait, auto-click buttons, multiple snapshots
                selenium_wait = 15 if is_js_heavy else 12  # Tăng thời gian đợi
                selenium_result = scrape_with_selenium(url, max_length=max_length, wait_time=selenium_wait)
                
                if selenium_result.get('success') and len(selenium_result.get('content', '')) > 200:
                    selenium_content = selenium_result['content']
                    selenium_buttons_clicked = selenium_result.get('buttons_clicked', 0)
                    selenium_snapshots = selenium_result.get('snapshots', 1)
                    selenium_screenshot = selenium_result.get('screenshot_base64')
                    
                    print(f"[URL SCRAPE] Selenium: {len(selenium_content)} chars, clicked {selenium_buttons_clicked} buttons, {selenium_snapshots} snapshots")
                    if selenium_screenshot:
                        print(f"[URL SCRAPE] Screenshot captured: {len(selenium_screenshot)} chars base64")
                    
                    # Get extracted links from Selenium
                    if selenium_result.get('extracted_links'):
                        extracted_links = selenium_result['extracted_links']
                        print(f"[URL SCRAPE] Selenium found {len(extracted_links)} related links")
                    
                    # Use Selenium content if significantly longer or more complete
                    if len(selenium_content) > len(full_content) * 0.7 or len(full_content) < 1500:
                        full_content = selenium_content
                        if selenium_result.get('title') and selenium_result['title'] != url:
                            title = selenium_result['title']
                        print(f"[URL SCRAPE] Using Selenium deep-scraped content ({len(full_content)} chars)")
                        
                        # Store screenshot for later use
                        if selenium_screenshot:
                            screenshot_base64 = selenium_screenshot
                else:
                    print(f"[URL SCRAPE] Selenium returned insufficient content: {len(selenium_result.get('content', ''))} chars")
            except Exception as e:
                print(f"[URL SCRAPE] Selenium failed: {e}")
                import traceback
                traceback.print_exc()

        # Add metadata header
        header_parts = [f"Title: {title}"]
        if author:
            header_parts.append(f"Author: {author}")
        if date:
            header_parts.append(f"Date: {date}")
        header_parts.append(f"URL: {url}")
        header_parts.append("="*50)

        content_with_header = '\n'.join(header_parts) + '\n\n' + full_content

        # Truncate if too long
        if len(content_with_header) > max_length:
            content_with_header = content_with_header[:max_length] + "\n\n... [Content truncated - too long]"

        # Check if screenshot exists and is valid
        screenshot_data = None
        if 'screenshot_base64' in dir() and screenshot_base64:
            if len(screenshot_base64) < 700000:  # ~500KB limit
                screenshot_data = screenshot_base64
            else:
                print(f"[URL SCRAPE] Screenshot too large, not including in result")
        
        result = {
            'url': url,
            'title': title,
            'content': content_with_header,
            'success': True,
            'error': None,
            'author': author,
            'date': date,
            'source': 'trafilatura+bs4+selenium-deep',
            'extracted_links': extracted_links[:20],  # Limit to 20 links
            'screenshot_base64': screenshot_data,
            'has_screenshot': screenshot_data is not None,
            'scraping_metadata': {
                'buttons_clicked': selenium_buttons_clicked,
                'snapshots': selenium_snapshots,
                'final_content_length': len(full_content),
                'has_screenshot': screenshot_data is not None
            }
        }

        # Cache the result
        _url_scrape_cache[url] = result
        content_preview = content_with_header[:100].replace('\n', ' ')
        link_count = len(extracted_links)
        has_ss = "📸" if screenshot_data else ""
        print(f"[URL SCRAPE] SUCCESS: {url[:60]}... | Title: {title[:50]}... | Content: {len(content_with_header)} chars | Links: {link_count} | Buttons: {selenium_buttons_clicked} {has_ss}")
        return result

    except Exception as e:
        error_msg = str(e)
        print(f"[URL SCRAPE] Failed for {url}: {error_msg}")
        result = {
            'url': url,
            'title': url,
            'content': "",
            'success': False,
            'error': error_msg
        }
        _url_scrape_cache[url] = result
        return result


def simple_scrape_url(url, timeout=30):
    """
    Simple HTTP-only scraping as fallback when full scrape fails.
    PHASE 2: Fast, reliable fallback without Selenium.
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    
    print(f"[SIMPLE SCRAPE] Fetching {url} (timeout={timeout}s)")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        
        # Handle 403 specifically
        if response.status_code == 403:
            print(f"[SIMPLE SCRAPE] 403 Forbidden - website blocks scrapers: {url}")
            return {
                'url': url,
                'title': url,
                'content': f"Website {url} đang chặn truy cập tự động (403 Forbidden). Thử tìm nguồn khác hoặc copy-paste nội dung.",
                'success': False,
                'error': '403 Forbidden - Website blocks automated access'
            }
        
        response.raise_for_status()
        
        html = response.text
        print(f"[SIMPLE SCRAPE] Got HTML: {len(html)} chars")
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript', 'advertisement', '.ad', '.ads', '.sidebar', '.comment', '.comments']):
            tag.decompose()
        
        # Get title
        title = url
        if soup.find('title'):
            title = soup.find('title').get_text(strip=True)
        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        
        # Extract content - simple approach
        content_parts = []
        
        # Try main content areas
        main_selectors = ['main', 'article', '[role="main"]', '.content', '.post-content', '.entry-content', '#content']
        for selector in main_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator='\n', strip=True)
                if len(text) > 200:
                    content_parts.append(text)
                    print(f"[SIMPLE SCRAPE] Found content with selector: {selector} ({len(text)} chars)")
                    break
        
        # Fallback: get all paragraphs and headings
        if not content_parts:
            paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
            texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 20:
                    texts.append(text)
            if texts:
                content_parts.append('\n\n'.join(texts))
                print(f"[SIMPLE SCRAPE] Extracted {len(texts)} text elements")
        
        # Final fallback: body text
        if not content_parts:
            body = soup.find('body')
            if body:
                all_text = body.get_text(separator='\n', strip=True)
                content_parts.append(all_text)
                print(f"[SIMPLE SCRAPE] Used body text: {len(all_text)} chars")
        
        content = '\n\n'.join(content_parts)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Add header
        full_content = f"Title: {title}\nURL: {url}\n{'='*50}\n\n{content}"
        
        print(f"[SIMPLE SCRAPE] SUCCESS: {len(full_content)} chars")
        
        return {
            'url': url,
            'title': title,
            'content': full_content,
            'success': len(content) > 100,
            'error': None
        }
        
    except requests.exceptions.Timeout:
        print(f"[SIMPLE SCRAPE] Timeout after {timeout}s")
        return {
            'url': url,
            'title': url,
            'content': "",
            'success': False,
            'error': f'Request timeout after {timeout} seconds'
        }
    except requests.exceptions.RequestException as e:
        print(f"[SIMPLE SCRAPE] Request error: {e}")
        return {
            'url': url,
            'title': url,
            'content': "",
            'success': False,
            'error': f'Request failed: {str(e)}'
        }
    except Exception as e:
        print(f"[SIMPLE SCRAPE] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'url': url,
            'title': url,
            'content': "",
            'success': False,
            'error': str(e)
        }


def extract_urls_from_text(text):
    """Extract HTTP/HTTPS URLs from user text."""
    url_pattern = r'https?://[^\s<>"\')\]]+(?:[^\s<>"\')\]]|(?<=\.[a-zA-Z])/(?=[^\s]))*'
    urls = re.findall(url_pattern, text)
    return list(set(urls))  # Remove duplicates


def parse_import_urls_tag(text):
    """Parse [IMPORT_URLS: url1, url2, ...] tag from AI response."""
    pattern = r'\[IMPORT_URLS:\s*([^\]]+)\]'
    match = re.search(pattern, text)
    if match:
        urls_str = match.group(1)
        # Split by comma and clean up
        urls = [url.strip() for url in urls_str.split(',') if url.strip()]
        return urls, match
    return [], None


def generate_stream_response(conversation, user_text, model_id="gemini-2.0-flash", notebook_context=None, gemini_files=None, search_mode=False):
    """
    Yield SSE-formatted chunks of the response.
    Pure Gemini ecosystem - no third-party providers.
    notebook_context: Optional string from Notebook LLM to ground responses
    gemini_files: Optional list of Gemini File objects/URIs to send with message
    search_mode: Boolean to enable/disable web search (default False)
    """
    # Validate user input is not empty
    if not user_text or not user_text.strip():
        yield "data: [ERROR] Tin nhắn trống. Vui lòng nhập nội dung.\n\n"
        yield "data: [DONE]\n\n"
        return
    
    # Validate API key
    if not settings.GEMINI_API_KEY:
        yield "data: [ERROR] GEMINI_API_KEY not configured\n\n"
        yield "data: [DONE]\n\n"
        return
    
    # Phase 5.1: Perform web search ONLY when search_mode is enabled
    search_results = []
    if search_mode:
        print(f"[SEARCH MODE] Enabled - performing web search for: '{user_text[:50]}...'")
        search_results = perform_web_search(user_text, max_results=5)
    else:
        print(f"[SEARCH MODE] Disabled - using model knowledge only")
    
    # Prepare sources for frontend
    sources_for_frontend = []
    search_context = ""
    
    if search_results:
        # Format for frontend (sources chips)
        sources_for_frontend = [
            {"title": r.get('title', ''), "url": r.get('href', '')}
            for r in search_results
        ]
        
        # Format search context for Gemini
        search_context_parts = []
        for i, result in enumerate(search_results, 1):
            search_context_parts.append(
                f"[{i}] {result.get('title', '')}\nURL: {result.get('href', '')}\n{result.get('body', '')}"
            )
        search_context = "\n\n".join(search_context_parts)
    
    # Configure Gemini
    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    # Fetch last 10 messages for context
    past_messages = conversation.messages.all().order_by('-created_at')[:10]
    past_messages = list(reversed(past_messages))
    
    # Build conversation history - filter out empty messages
    history = []
    for msg in past_messages:
        role = 'user' if msg.role == 'user' else 'model'
        content = msg.content or ""  # Handle None
        if not content.strip():  # Skip empty messages
            continue
        if msg.thinking_process:
            content = f"<thinking>\n{msg.thinking_process}\n</thinking>\n{content}"
        history.append({"role": role, "parts": [content]})
    
    # Real-time System Prompt Injection - Dynamic per request with Vietnam timezone
    hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    current_time = datetime.datetime.now(hcm_tz)
    current_time_str = current_time.strftime('%H:%M:%S, ngày %d/%m/%Y')
    current_date_only = current_time.strftime('%d/%m/%Y')

    # Dynamic instruction based on search mode
    if search_mode:
        dynamic_instruction = f'''Hôm nay là {current_time_str}. Bạn là Nova AI - Real-Time Web Agent.

SEARCH MODE: BẬT - Người dùng đã yêu cầu tìm kiếm thông tin.
QUY TẮC KHI TÌM KIẾM:
1. Sử dụng thông tin tìm kiếm được được cung cấp để trả lời.
2. Phân tích các nguồn trong <thinking> trước khi trả lời.
3. Trích dẫn nguồn theo cách tự nhiên: "Theo [tên website]..." hoặc "Từ nguồn [tên]..."
4. KHÔNG đánh số [1], [2], [3] trong văn bản - chỉ liệt kê nguồn ở cuối nếu cần.
5. Kết quả cuối cùng VIẾT BÊN NGOÀI thẻ </thinking>.
'''
    else:
        dynamic_instruction = f'''Hôm nay là {current_time_str}. Bạn là Nova AI - Trợ lý thông minh.

SEARCH MODE: TẮT - Trả lời dựa trên kiến thức của bạn.
QUY TẮC:
1. Không cần tìm kiếm web, trả lời trực tiếp dựa trên kiến thức đã có.
2. Định dạng suy nghĩ trong <thinking>...</thinking>
3. Kết quả cuối cùng VIẾT BÊN NGOÀI thẻ </thinking>.
4. Chỉ khi người dùng yêu cầu thông tin mới nhất/tin tức thì mới cần tìm kiếm.
'''
    
    # Build enhanced system instruction
    instruction_parts = [SYSTEM_INSTRUCTION, dynamic_instruction]
    
    # Add notebook context to system instruction (not user message)
    if notebook_context:
        instruction_parts.append(f"\n\n=== NOTEBOOK LLM SOURCES ===\n{notebook_context}\n=== END NOTEBOOK SOURCES ===")
    
    # Add search context if available (only when search_mode is enabled)
    if search_mode and search_context:
        instruction_parts.append(f"\n\nDưới đây là thông tin tìm kiếm được từ web:\n{search_context}")
        instruction_parts.append("Hãy phân tích các nguồn này và trích dẫn tự nhiên, không đánh số.")
    
    enhanced_system_instruction = "\n\n".join(instruction_parts)
    
    # Initialize model with enhanced system instruction
    model = genai.GenerativeModel(
        model_name=model_id,
        system_instruction=enhanced_system_instruction
    )
    
    try:
        # Enable Google Search tool for Gemini 1.5+ models
        tools = None
        if model_id in ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-2.0-pro']:
            tools = [{'google_search': {}}]
        
        # Start chat with history
        chat = model.start_chat(history=history)
        
        # Prepare message content - include files if available
        message_content = user_text
        if gemini_files and len(gemini_files) > 0:
            # Create a list of file references and text
            message_parts = []
            for file_uri in gemini_files:
                try:
                    # Extract file ID from full URI if needed
                    # Full URI: https://generativelanguage.googleapis.com/v1beta/files/abc123
                    # Need just: files/abc123 or abc123
                    if '/' in file_uri and 'files/' in file_uri:
                        # Extract the file resource name (e.g., "files/abc123")
                        file_id = file_uri.split('files/')[-1]
                        file_ref = f"files/{file_id}"
                    else:
                        file_ref = file_uri

                    # Get the file object from Gemini using resource name
                    file_obj = genai.get_file(file_ref)
                    message_parts.append(file_obj)
                    print(f"[Gemini] Attached file: {file_ref}")
                except Exception as e:
                    error_str = str(e)
                    # Handle 403 - file expired or no permission
                    if '403' in error_str or 'permission' in error_str.lower() or 'not exist' in error_str.lower():
                        print(f"[Gemini] File expired or no permission (403), skipping: {file_ref}")
                        # Continue without this file - don't add to message_parts
                        continue
                    print(f"[Gemini] Failed to attach file {file_uri}: {e}")
            
            # Add text after files
            message_parts.append(user_text)
            message_content = message_parts
            print(f"[Gemini] Sending message with {len(gemini_files)} file(s)")
        
        # TASK 4: Generate streaming response with search grounding
        response = chat.send_message(
            message_content, 
            stream=True,
            tools=tools if tools else None
        )
        
        full_response = ""
        grounding_sources = []  # Collect sources from Gemini grounding
        
        for chunk in response:
            # Extract text content
            if chunk.text:
                text = chunk.text
                full_response += text
                # Properly escape newlines for SSE format
                safe_text = text.replace('\n', '\\n').replace('\r', '\\r')
                yield f"data: {safe_text}\n\n"
            
            # Extract grounding metadata from Gemini's Google Search results
            if hasattr(chunk, 'candidates') and chunk.candidates:
                for candidate in chunk.candidates:
                    if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
                        metadata = candidate.grounding_metadata
                        # Extract web search results from grounding chunks
                        if hasattr(metadata, 'grounding_chunks'):
                            for chunk_data in metadata.grounding_chunks:
                                # Gemini SDK v0.8+: chunk_data.web has .title and .uri
                                if hasattr(chunk_data, 'web'):
                                    web_data = chunk_data.web
                                    title = getattr(web_data, 'title', '') or getattr(web_data, 'title_', '')
                                    uri = getattr(web_data, 'uri', '') or getattr(web_data, 'uri_', '') or getattr(web_data, 'url', '')
                                    if title and uri:
                                        grounding_sources.append({
                                            'title': title,
                                            'url': uri
                                        })
                                # Older SDK versions: direct attributes
                                elif hasattr(chunk_data, 'title') or hasattr(chunk_data, 'uri'):
                                    title = getattr(chunk_data, 'title', '') or getattr(chunk_data, 'title_', '')
                                    uri = getattr(chunk_data, 'uri', '') or getattr(chunk_data, 'uri_', '') or getattr(chunk_data, 'url', '')
                                    if title and uri:
                                        grounding_sources.append({
                                            'title': title,
                                            'url': uri
                                        })
                        
                        # Alternative: Extract from search entry point if available
                        if hasattr(metadata, 'search_entry_point') and metadata.search_entry_point:
                            sep = metadata.search_entry_point
                            if hasattr(sep, 'rendered_content'):
                                print(f"[SEARCH ENTRY] {sep.rendered_content}")
            
            # Force immediate flush to prevent chunking
            import sys
            sys.stdout.flush()
        
        # Merge DuckDuckGo sources with Gemini grounding sources (prefer Gemini for accuracy)
        final_sources = grounding_sources if grounding_sources else sources_for_frontend
        
        # Phase 5.1: Yield sources as first chunk if available
        if final_sources:
            sources_json = json.dumps(final_sources)
            yield f"data: <sources>{sources_json}</sources>\n\n"
        
        # Parse and save response
        _save_ai_response(conversation, full_response, sources_json if final_sources else "")
        
    except Exception as e:
        error_msg = str(e)
        if "API key not valid" in error_msg or "invalid" in error_msg.lower():
            yield "data: [Lỗi hệ thống] API key không hợp lệ. Vui lòng kiểm tra cấu hình.\n\n"
        elif "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower() or "rate limit" in error_msg.lower():
            # Specific 429/quota error message as requested - no fake <thinking> tags
            yield "data: [Hết hạn mức API] Google API hiện tại đã hết lượt sử dụng. Vui lòng đổi API Key mới trong file .env hoặc đợi vài phút rồi thử lại.\n\n"
        else:
            yield f"data: [ERROR] Gemini Error: {error_msg}\n\n"
        return
    
    # Signal end of stream
    yield "data: [DONE]\n\n"


def _save_ai_response(conversation, full_response, sources_json=""):
    """Parse thinking tags and save AI response to database."""
    # Parse <thinking> tags from full_response
    think_match = re.search(r'<thinking>(.*?)</thinking>', full_response, flags=re.DOTALL)
    
    thinking_process = ""
    content = full_response
    
    if think_match:
        thinking_process = think_match.group(1).strip()
        # Remove think tags from the final text
        content = re.sub(r'<thinking>.*?</thinking>', '', full_response, flags=re.DOTALL).strip()
    
    # Save the AI response
    Message.objects.create(
        conversation=conversation,
        role='model',
        content=content,
        thinking_process=thinking_process,
        sources=sources_json
    )
    print(f"[PERSISTENCE] AI response saved to conversation {conversation.id}")


def generate_conversation_title(user_text, model_id="gemini-1.5-flash"):
    """Generate a concise 3-word title for a new conversation using Gemini."""
    if not settings.GEMINI_API_KEY:
        return "Cuộc hội thoại mới"

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name=model_id)

        prompt = (
            f'Tạo tiêu đề ngắn gọn 2-4 từ bằng tiếng Việt cho cuộc hội thoại '
            f'bắt đầu với: "{user_text[:100]}". '
            f'Chỉ trả về tiêu đề, không giải thích, không dấu ngoặc.'
        )

        response = model.generate_content(prompt)
        title = response.text.strip().strip('"').strip("'")
        return title[:50] if title else "Cuộc hội thoại mới"

    except Exception as e:
        print(f"[ERROR] Title generation failed: {e}")
        # Fallback to first 5 words of user message
        words = user_text.strip().split()[:5]
        fallback_title = " ".join(words) if words else "Cuộc hội thoại mới"
        return fallback_title[:50]


def generate_text_sync(prompt, model_name="gemini-2.0-flash", temperature=0.7):
    """
    Generate text synchronously (non-streaming) using Gemini.
    Simple wrapper for one-off text generation.
    """
    if not settings.GEMINI_API_KEY:
        return "[Error: Gemini API key not configured]"
    
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(model_name=model_name)
        
        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': temperature,
                'max_output_tokens': 2048,
            }
        )
        
        return response.text.strip()
        
    except Exception as e:
        print(f"[ERROR] generate_text_sync failed: {e}")
        return f"[Error: {str(e)}]"


class GeminiVisionService:
    """
    Gemini Vision Service for processing images and multimodal content.
    Provides image analysis, OCR, and visual understanding capabilities.
    """

    @staticmethod
    def process_image_with_vision(image_b64, prompt="Phân tích chi tiết hình ảnh này:"):
        """
        Process an image using Gemini Vision API.
        Supports base64 encoded images.

        Args:
            image_b64: Base64 encoded image string
            prompt: Custom prompt for image analysis

        Returns:
            str: Analysis result from Gemini Vision
        """
        if not settings.GEMINI_API_KEY:
            return "[Error: Gemini API key not configured]"

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)

            # Use Gemini 2.0 Flash for vision tasks (supports multimodal)
            model = genai.GenerativeModel(model_name="gemini-2.0-flash")

            # Decode base64 and create image part
            import base64
            image_bytes = base64.b64decode(image_b64)

            # Create content with both image and text
            content = [
                {
                    "mime_type": "image/jpeg",  # Will auto-detect if different
                    "data": image_bytes
                },
                prompt
            ]

            # Generate response
            response = model.generate_content(content)
            analysis = response.text

            print(f"[Vision] Image processed: {len(analysis)} chars extracted")
            return analysis

        except Exception as e:
            print(f"[Vision Error] Failed to process image: {e}")
            return f"[Lỗi phân tích ảnh: {str(e)}]"

    @staticmethod
    def process_multiple_images(image_b64_list, prompt="Phân tích các hình ảnh này:"):
        """
        Process multiple images at once using Gemini Vision.

        Args:
            image_b64_list: List of base64 encoded image strings
            prompt: Custom prompt for analysis

        Returns:
            str: Combined analysis result
        """
        if not settings.GEMINI_API_KEY:
            return "[Error: Gemini API key not configured]"

        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(model_name="gemini-2.0-flash")

            import base64

            # Build content array with multiple images
            content = []
            for img_b64 in image_b64_list:
                image_bytes = base64.b64decode(img_b64)
                content.append({
                    "mime_type": "image/jpeg",
                    "data": image_bytes
                })

            content.append(prompt)

            response = model.generate_content(content)
            return response.text

        except Exception as e:
            print(f"[Vision Error] Failed to process multiple images: {e}")
            return f"[Lỗi phân tích nhiều ảnh: {str(e)}]"


# Global service instance
AI_SERVICE = GeminiVisionService()
