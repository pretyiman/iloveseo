from dataclasses import dataclass, field

# Signal strength, mirroring Wappalyzer's own weighting convention:
# strong=50, medium=30, weak=15. A technology is only counted once per
# signal even if a pattern happens to match multiple times.
STRONG = 50
MEDIUM = 30
WEAK = 15


@dataclass
class Signal:
    source: str  # "html" | "header" | "cookie" | "meta_generator"
    pattern: str
    header_name: str | None = None
    weight: int = MEDIUM


@dataclass
class Signature:
    name: str
    category: str
    signals: list[Signal] = field(default_factory=list)


SIGNATURES: list[Signature] = [
    # --- CMS ---
    Signature("WordPress", "CMS", [
        Signal("html", r"/wp-content/", weight=STRONG),
        Signal("html", r"/wp-includes/", weight=MEDIUM),
        Signal("meta_generator", r"WordPress", weight=STRONG),
    ]),
    Signature("Shopify", "CMS", [
        Signal("html", r"cdn\.shopify\.com", weight=STRONG),
        Signal("html", r"Shopify\.theme", weight=MEDIUM),
        Signal("header", r".+", header_name="x-shopid", weight=STRONG),
    ]),
    Signature("Wix", "CMS", [
        Signal("html", r"static\.wixstatic\.com", weight=STRONG),
        Signal("html", r"wix-viewer|_wixCIDX", weight=MEDIUM),
    ]),
    Signature("Squarespace", "CMS", [
        Signal("html", r"static1\.squarespace\.com", weight=STRONG),
        Signal("meta_generator", r"Squarespace", weight=STRONG),
    ]),
    Signature("Webflow", "CMS", [
        Signal("html", r"assets-global\.website-files\.com", weight=STRONG),
        Signal("html", r"data-wf-site", weight=MEDIUM),
    ]),
    Signature("Drupal", "CMS", [
        Signal("html", r"Drupal\.settings|drupal\.js", weight=MEDIUM),
        Signal("meta_generator", r"Drupal", weight=STRONG),
        Signal("header", r"Drupal", header_name="x-generator", weight=STRONG),
    ]),
    Signature("Joomla", "CMS", [
        Signal("meta_generator", r"Joomla", weight=STRONG),
        Signal("html", r"/media/jui/", weight=MEDIUM),
    ]),
    Signature("Magento", "CMS", [
        Signal("html", r"Mage\.Cookies|mage/cookies\.js", weight=MEDIUM),
        Signal("html", r"/static/version\d+/frontend/", weight=MEDIUM),
    ]),
    Signature("BigCommerce", "CMS", [
        Signal("html", r"cdn\d*\.bigcommerce\.com|bigcommerce\.com/s-", weight=STRONG),
    ]),
    Signature("Ghost", "CMS", [
        Signal("meta_generator", r"Ghost", weight=STRONG),
        Signal("html", r"/ghost/", weight=WEAK),
    ]),
    Signature("HubSpot CMS", "CMS", [
        Signal("html", r"hs-scripts\.com|hubspot\.com/cs", weight=MEDIUM),
    ]),
    Signature("Next.js", "CMS", [
        Signal("html", r"__NEXT_DATA__|_next/static", weight=STRONG),
    ]),
    Signature("Nuxt.js", "CMS", [
        Signal("html", r"__NUXT__|/_nuxt/", weight=STRONG),
    ]),
    Signature("Gatsby", "CMS", [
        Signal("html", r"__gatsby|/page-data/", weight=MEDIUM),
    ]),
    Signature("Astro", "CMS", [
        Signal("html", r"astro-island", weight=MEDIUM),
    ]),
    Signature("SvelteKit", "CMS", [
        Signal("html", r"__sveltekit", weight=MEDIUM),
    ]),
    Signature("Remix", "CMS", [
        Signal("html", r"__remixContext", weight=MEDIUM),
    ]),

    # --- Web Servers ---
    Signature("Nginx", "Web Servers", [Signal("header", r"nginx", header_name="server", weight=STRONG)]),
    Signature("Apache", "Web Servers", [Signal("header", r"Apache", header_name="server", weight=STRONG)]),
    Signature("LiteSpeed", "Web Servers", [Signal("header", r"LiteSpeed", header_name="server", weight=STRONG)]),
    Signature("Microsoft IIS", "Web Servers", [Signal("header", r"Microsoft-IIS", header_name="server", weight=STRONG)]),
    Signature("Caddy", "Web Servers", [Signal("header", r"Caddy", header_name="server", weight=MEDIUM)]),
    Signature("Vercel", "Web Servers", [
        Signal("header", r".+", header_name="x-vercel-id", weight=STRONG),
        Signal("header", r"Vercel", header_name="server", weight=MEDIUM),
    ]),
    Signature("Netlify", "Web Servers", [
        Signal("header", r"Netlify", header_name="server", weight=STRONG),
        Signal("header", r".+", header_name="x-nf-request-id", weight=STRONG),
    ]),

    # --- CSS Frameworks ---
    Signature("Bootstrap", "CSS Frameworks", [
        Signal("html", r"bootstrap(\.min)?\.css", weight=MEDIUM),
        Signal("html", r"bootstrap\.bundle(\.min)?\.js", weight=MEDIUM),
    ]),
    Signature("Tailwind CSS", "CSS Frameworks", [Signal("html", r"tailwindcss|tailwind(\.min)?\.css", weight=MEDIUM)]),
    Signature("Bulma", "CSS Frameworks", [Signal("html", r"bulma(\.min)?\.css", weight=STRONG)]),
    Signature("Foundation", "CSS Frameworks", [Signal("html", r"foundation(\.min)?\.css", weight=MEDIUM)]),

    # --- Ecommerce platforms ---
    Signature("WooCommerce", "Ecommerce", [
        Signal("html", r"woocommerce", weight=STRONG),
        Signal("cookie", r"woocommerce_", weight=MEDIUM),
    ]),
    Signature("PrestaShop", "Ecommerce", [Signal("meta_generator", r"PrestaShop", weight=STRONG)]),
    Signature("OpenCart", "Ecommerce", [
        Signal("html", r"index\.php\?route=", weight=WEAK),
        Signal("meta_generator", r"OpenCart", weight=STRONG),
    ]),
    Signature("Salesforce Commerce Cloud", "Ecommerce", [Signal("html", r"demandware\.static|dwstatic", weight=STRONG)]),

    # --- JavaScript libraries/frameworks ---
    Signature("React", "JavaScript", [
        Signal("html", r"data-reactroot|react-dom(\.min)?\.js", weight=MEDIUM),
    ]),
    Signature("Vue.js", "JavaScript", [Signal("html", r"__vue__|data-v-[0-9a-f]{8}", weight=MEDIUM)]),
    Signature("Angular", "JavaScript", [Signal("html", r"ng-version=|ng-app", weight=MEDIUM)]),
    Signature("jQuery", "JavaScript", [Signal("html", r"jquery(-[\d.]+)?(\.min)?\.js", weight=MEDIUM)]),
    Signature("Alpine.js", "JavaScript", [Signal("html", r"alpinejs|x-data=", weight=MEDIUM)]),
    Signature("htmx", "JavaScript", [Signal("html", r"htmx\.org|hx-get=", weight=MEDIUM)]),
    Signature("Svelte", "JavaScript", [Signal("html", r"svelte-[a-z0-9]{6}", weight=WEAK)]),

    # --- Page Builders ---
    Signature("Elementor", "Page Builders", [
        Signal("html", r"elementor-widget", weight=MEDIUM),
        Signal("html", r"elementor", weight=WEAK),
    ]),
    Signature("Divi", "Page Builders", [Signal("html", r"et_pb_section|divi-theme", weight=MEDIUM)]),
    Signature("Beaver Builder", "Page Builders", [Signal("html", r"fl-builder|beaver-builder", weight=MEDIUM)]),
    Signature("WPBakery", "Page Builders", [Signal("html", r"js_composer|wpb_wrapper", weight=MEDIUM)]),
    Signature("Oxygen Builder", "Page Builders", [Signal("html", r"oxygen-theme|ct-section", weight=WEAK)]),

    # --- WordPress Themes ---
    # The most reliable real-world signal for a WP theme is its slug
    # appearing in the /wp-content/themes/<slug>/ asset path Wordpress
    # itself generates -- more reliable than hoping the theme's own CSS
    # classes leak into the markup.
    Signature("Astra", "WordPress Themes", [
        Signal("html", r"/themes/astra/", weight=MEDIUM),
        Signal("html", r"ast-container", weight=WEAK),
    ]),
    Signature("OceanWP", "WordPress Themes", [
        Signal("html", r"/themes/oceanwp/", weight=MEDIUM),
        Signal("html", r"oceanwp", weight=WEAK),
    ]),
    Signature("GeneratePress", "WordPress Themes", [
        Signal("html", r"/themes/generatepress/", weight=MEDIUM),
        Signal("html", r"generatepress", weight=WEAK),
    ]),
    Signature("Avada", "WordPress Themes", [
        Signal("html", r"/themes/avada/", weight=MEDIUM),
        Signal("html", r"fusion-builder", weight=WEAK),
    ]),

    # --- WordPress Plugins ---
    Signature("Yoast SEO", "WordPress Plugins", [Signal("html", r"Yoast SEO plugin|class=\"yoast", weight=STRONG)]),
    Signature("Rank Math", "WordPress Plugins", [Signal("html", r"rank-math", weight=MEDIUM)]),
    Signature("Contact Form 7", "WordPress Plugins", [Signal("html", r"wpcf7", weight=MEDIUM)]),
    Signature("WP Rocket", "WordPress Plugins", [Signal("html", r"wp-rocket", weight=WEAK)]),
    Signature("Jetpack", "WordPress Plugins", [Signal("html", r"jetpack", weight=WEAK)]),

    # --- CDNs ---
    Signature("Cloudflare", "CDN", [
        Signal("header", r"cloudflare", header_name="server", weight=STRONG),
        Signal("header", r".+", header_name="cf-ray", weight=STRONG),
    ]),
    Signature("Fastly", "CDN", [Signal("header", r".+", header_name="x-fastly-request-id", weight=STRONG)]),
    Signature("Akamai", "CDN", [Signal("header", r"AkamaiGHost", header_name="server", weight=STRONG)]),
    Signature("AWS CloudFront", "CDN", [Signal("header", r".+", header_name="x-amz-cf-id", weight=STRONG)]),
]
