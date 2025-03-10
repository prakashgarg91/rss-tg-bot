# Fix for feedparser with Python 3.13+
import sys

# Check if cgi module exists, if not create a minimal shim
if "cgi" not in sys.modules:
    import html
    
    class MiniCGI:
        def escape(self, string, quote=True):
            return html.escape(string, quote=quote)
    
    sys.modules["cgi"] = MiniCGI()
    
    print("Applied CGI module shim for feedparser compatibility")