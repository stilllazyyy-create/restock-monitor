
import json
from datetime import datetime, timezone
import os
import time
import urllib.error
import urllib.request


# ============================================================
# SETTINGS
# ============================================================

STATE_FILE = ".restock_state.json"

STORE_URL = "https://ca.stussy.com"

NEW_ARRIVALS_URL = (
    "https://ca.stussy.com/collections/new-arrivals"
)

check_started_at = datetime.now(timezone.utc).isoformat()
check_errors = []

webhook = os.environ.get(
    "DISCORD_WEBHOOK_URL"
)

if not webhook:
    raise RuntimeError(
        "DISCORD_WEBHOOK_URL secret is missing"
    )


RETRY_DELAYS = [3, 7, 15]

RETRY_HTTP_CODES = {
    429,
    500,
    502,
    503,
    504,
}


TARGETS = [
    {
        "name": "Skulls Tee",
        "url": (
            "https://ca.stussy.com/products/"
            "1905177-skulls-tee-faded-black"
        ),
        "variants": {
            52765121773936: "Faded Black / S",
        },
    },

    {
        "name": "Always World Tour Tee Black",
        "url": (
            "https://ca.stussy.com/products/"
            "3904050-stussy-always-world-tour-tee-black"
        ),
        "variants": {
            54012844278128: "Black / S",
            54012844310896: "Black / M",
        },
    },

    {
        "name": "Always World Tour Tee White",
        "url": (
            "https://ca.stussy.com/products/"
            "3904050-stussy-always-world-tour-tee-white"
        ),
        "variants": {
            54012851552624: "White / S",
            54012851585392: "White / M",
        },
    },

    {
        "name": "Basic Stussy Thermal",
        "url": (
            "https://ca.stussy.com/products/"
            "1140356-basic-stussy-thermal-washed-black"
        ),
        "variants": {
            52349784162672: "Washed Black / S",
            52349784195440: "Washed Black / M",
            52349784228208: "Washed Black / L",
        },
    },
]


# ============================================================
# LOAD STATE
# ============================================================

try:
    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        state = json.load(f)

except FileNotFoundError:
    state = {}


# ============================================================
# HTTP FETCH
# ============================================================

def fetch_json(url):

    attempts = (
        len(RETRY_DELAYS) + 1
    )

    for attempt in range(
        attempts
    ):

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(iPhone; CPU iPhone OS 18_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 "
                    "(KHTML, like Gecko) "
                    "Version/18.0 Mobile/15E148 Safari/604.1"
                ),
                "Accept": (
                    "application/json,"
                    "text/plain,*/*"
                ),
                "Accept-Language": (
                    "en-CA,en;q=0.9"
                ),
                "Cache-Control": (
                    "no-cache"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                req,
                timeout=25
            ) as response:

                data = response.read()

                if not data:
                    raise RuntimeError(
                        "Empty response"
                    )

                return json.loads(
                    data.decode(
                        "utf-8"
                    )
                )


        except urllib.error.HTTPError as e:

            if (
                e.code
                in RETRY_HTTP_CODES
                and attempt
                < len(RETRY_DELAYS)
            ):

                delay = (
                    RETRY_DELAYS[
                        attempt
                    ]
                )

                print(
                    f"HTTP {e.code} "
                    f"fetching {url}. "
                    f"Retrying in "
                    f"{delay}s..."
                )

                time.sleep(
                    delay
                )

                continue

            raise


        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            RuntimeError,
            json.JSONDecodeError,
        ) as e:

            if (
                attempt
                < len(RETRY_DELAYS)
            ):

                delay = (
                    RETRY_DELAYS[
                        attempt
                    ]
                )

                print(
                    f"Fetch error: {e}. "
                    f"Retrying in "
                    f"{delay}s..."
                )

                time.sleep(
                    delay
                )

                continue

            raise


    raise RuntimeError(
        f"Unable to fetch {url}"
    )


# ============================================================
# DISCORD
# ============================================================

def send_discord_payload(
    payload,
    max_retries=5
):

    data = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")


    for attempt in range(
        max_retries
    ):

        request = (
            urllib.request.Request(
                webhook,
                data=data,
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                    "User-Agent": (
                        "Stussy-Restock-Monitor/5.0"
                    ),
                },
                method="POST",
            )
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=25
            ) as response:

                response.read()

            return True


        except urllib.error.HTTPError as e:

            if e.code == 429:

                try:
                    body = (
                        e.read()
                        .decode(
                            "utf-8"
                        )
                    )

                    info = json.loads(
                        body
                    )

                    retry_after = float(
                        info.get(
                            "retry_after",
                            2
                        )
                    )

                except Exception:
                    retry_after = 2


                print(
                    "Discord rate limit. "
                    f"Waiting "
                    f"{retry_after}s..."
                )

                time.sleep(
                    retry_after
                    + 0.5
                )

                continue


            if (
                500
                <= e.code
                <= 599
            ):

                print(
                    "Discord temporary "
                    f"HTTP error: "
                    f"{e.code}"
                )

            else:

                print(
                    "Discord HTTP error: "
                    f"{e.code} "
                    f"{e.reason}"
                )


        except Exception as e:

            print(
                "Discord error: "
                f"{e}"
            )


        time.sleep(2)


    return False


def send_text(text):

    return (
        send_discord_payload(
            {
                "content": text
            }
        )
    )


# ============================================================
# RESTOCK MONITOR
# ============================================================

print("")
print(
    "=========================================="
)
print(
    "RESTOCK MONITOR"
)
print(
    "=========================================="
)


for product_info in TARGETS:

    product_url = (
        product_info["url"]
    )

    json_url = (
        product_url
        + ".js?v="
        + str(
            int(
                time.time()
            )
        )
    )


    try:

        product = fetch_json(
            json_url
        )


    except Exception as e:

        print(
            "ERROR fetching "
            f"{product_info['name']}: "
            f"{type(e).__name__}: "
            f"{e}"
        )

        check_errors.append(f"{product_info['name']}: {type(e).__name__}")
        # IMPORTANT:
        # Do not modify old state
        # when a product fetch fails.
        continue


    variant_lookup = {
        int(v["id"]): v
        for v
        in product.get(
            "variants",
            []
        )
        if v.get("id")
    }


    for (
        variant_id,
        expected_title
    ) in product_info[
        "variants"
    ].items():


        variant = (
            variant_lookup.get(
                variant_id
            )
        )


        if not variant:

            print(
                "ERROR: "
                f"{product_info['name']} | "
                f"{expected_title} | "
                "variant not found"
            )

            check_errors.append(f"Missing variant {variant_id}")
            # Keep old state.
            continue


        if not isinstance(variant.get('available'), bool):
            check_errors.append(f"Invalid availability for variant {variant_id}")
            continue
        available = variant['available']


        key = (
            "variant_"
            + str(
                variant_id
            )
        )


        previous = (
            state.get(
                key
            )
        )


        print(
            f"{product_info['name']} | "
            f"{variant.get('title')} | "
            f"ID={variant_id} | "
            f"available={available} | "
            f"previous={previous}"
        )


        # ----------------------------------------------------
        # FIRST OBSERVATION
        # Baseline only. No alert.
        # ----------------------------------------------------

        if previous is None:

            state[key] = (
                available
            )

            print(
                "Baseline created: "
                f"{product_info['name']} | "
                f"{variant.get('title')}"
            )

            continue


        # ----------------------------------------------------
        # FALSE -> TRUE = REAL RESTOCK
        # ----------------------------------------------------

        if (
            available
            and previous is False
        ):

            image = (
                product.get(
                    "featured_image"
                )
            )


            embed = {
                "title": (
                    "🚨 STUSSY RESTOCK"
                ),

                "description": (
                    f"**{product_info['name']}**\n"
                    f"**{variant.get('title')}**\n\n"
                    "✅ **IN STOCK**\n"
                    "点击标题直接购买"
                ),

                "url": (
                    f"{product_url}"
                    f"?variant="
                    f"{variant_id}"
                ),
            }


            if image:

                if image.startswith(
                    "//"
                ):
                    image = (
                        "https:"
                        + image
                    )

                embed[
                    "image"
                ] = {
                    "url": image
                }


            success = (
                send_discord_payload(
                    {
                        "content": (
                            "🚨 **STUSSY 补货了！**"
                        ),
                        "embeds": [
                            embed
                        ],
                    }
                )
            )


            if success:

                print(
                    "RESTOCK "
                    "NOTIFICATION SENT: "
                    f"{product_info['name']} | "
                    f"{variant.get('title')}"
                )

                # Only mark TRUE after
                # Discord successfully sends.
                state[key] = True


            else:

                print(
                    "WARNING: "
                    "Restock Discord "
                    "notification failed."
                )

                print(
                    "Keeping previous "
                    "state FALSE so the "
                    "next run retries."
                )

                check_errors.append("Restock Discord delivery failed")
                state[key] = False


            continue


        # ----------------------------------------------------
        # ALL OTHER CASES
        # TRUE -> FALSE
        # TRUE -> TRUE
        # FALSE -> FALSE
        # ----------------------------------------------------

        state[key] = (
            available
        )


# ============================================================
# NEW ARRIVALS MONITOR
# ============================================================

print("")
print(
    "=========================================="
)
print(
    "NEW ARRIVALS MONITOR"
)
print(
    "=========================================="
)


try:

    products = []

    page = 1

    MAX_PAGES = 10


    # --------------------------------------------------------
    # FETCH ALL NEW ARRIVAL PAGES
    # --------------------------------------------------------

    while page <= MAX_PAGES:

        new_arrivals_json = (
            NEW_ARRIVALS_URL
            + "/products.json"
            + "?limit=250"
            + f"&page={page}"
            + "&v="
            + str(
                int(
                    time.time()
                )
            )
        )


        page_data = (
            fetch_json(
                new_arrivals_json
            )
        )


        page_products = (
            page_data.get(
                "products",
                []
            )
        )


        print(
            f"New Arrivals page "
            f"{page}: "
            f"{len(page_products)} "
            f"products"
        )


        products.extend(
            page_products
        )


        if (
            len(page_products)
            < 250
        ):
            break


        page += 1


    print(
        "New Arrivals total: "
        f"{len(products)} products"
    )


    # --------------------------------------------------------
    # BUILD CURRENT PRODUCT ID + HANDLE SETS
    # --------------------------------------------------------

    current_ids = set()

    current_handles = set()

    current_by_id = {}


    for product in products:

        product_id = (
            product.get(
                "id"
            )
        )

        handle = (
            product.get(
                "handle"
            )
        )


        if product_id is not None:

            product_id = str(
                product_id
            )

            current_ids.add(
                product_id
            )

            current_by_id[
                product_id
            ] = product


        if handle:

            current_handles.add(
                str(
                    handle
                )
            )


    # --------------------------------------------------------
    # LOAD PERMANENT HISTORY
    # --------------------------------------------------------

    old_ever_seen_ids = (
        state.get(
            "new_arrivals_ever_seen"
        )
    )

    old_ever_seen_handles = (
        state.get(
            "new_arrivals_ever_seen_handles"
        )
    )


    # ========================================================
    # MIGRATION / FIRST RUN
    # ========================================================

    if (
        old_ever_seen_ids
        is None
    ):

        old_current_ids = (
            state.get(
                "new_arrivals_products",
                []
            )
        )


        ever_seen_ids = {
            str(x)
            for x
            in old_current_ids
        }


        # Current products become baseline.
        ever_seen_ids.update(
            current_ids
        )


        ever_seen_handles = set(
            current_handles
        )


        print(
            "New Arrivals permanent "
            "history baseline created."
        )

        print(
            "No New Arrivals alert "
            "sent on migration run."
        )


    else:

        ever_seen_ids = {
            str(x)
            for x
            in old_ever_seen_ids
        }


        if (
            old_ever_seen_handles
            is None
        ):

            # First run after adding
            # handle protection.
            #
            # Current handles become baseline,
            # while old ID history is preserved.

            ever_seen_handles = set(
                current_handles
            )

            print(
                "Handle history "
                "baseline created."
            )

            print(
                "Existing ID history "
                "has been preserved."
            )


        else:

            ever_seen_handles = {
                str(x)
                for x
                in old_ever_seen_handles
            }


        # ----------------------------------------------------
        # A product is genuinely new ONLY if:
        #
        # 1. its Shopify ID has never been seen
        # AND
        # 2. its product handle has never been seen
        #
        # This prevents old products rebuilt by Shopify
        # under a new ID from being falsely reported.
        # ----------------------------------------------------

        truly_new_products = []


        for product in products:

            product_id = (
                product.get(
                    "id"
                )
            )

            handle = (
                product.get(
                    "handle"
                )
            )


            id_seen = False

            handle_seen = False


            if product_id is not None:

                id_seen = (
                    str(product_id)
                    in ever_seen_ids
                )


            if handle:

                handle_seen = (
                    str(handle)
                    in ever_seen_handles
                )


            if (
                not id_seen
                and not handle_seen
            ):

                truly_new_products.append(
                    product
                )


        print(
            "Current New Arrivals: "
            f"{len(products)}"
        )

        print(
            "Never-seen genuine "
            "new products: "
            f"{len(truly_new_products)}"
        )


        # ----------------------------------------------------
        # SEND NEW ARRIVAL ALERT
        # ----------------------------------------------------

        new_arrivals_success = True


        if truly_new_products:

            success = send_text(
                "🚨 **STUSSY NEW ARRIVALS**\n"
                "官网检测到 "
                f"**{len(truly_new_products)} 件"
                "真正新品**\n"
                f"{NEW_ARRIVALS_URL}"
            )


            if success:

                print(
                    "NEW ARRIVALS "
                    "NOTIFICATION SENT: "
                    f"{len(truly_new_products)} "
                    "product(s)"
                )


            else:

                new_arrivals_success = False
                check_errors.append("New Arrivals Discord delivery failed")

                print(
                    "WARNING: "
                    "New Arrivals Discord "
                    "notification failed."
                )

                print(
                    "New products will NOT "
                    "be added to permanent "
                    "history yet."
                )

                print(
                    "Next run will retry "
                    "the notification."
                )


        else:

            print(
                "No genuinely new "
                "arrivals detected."
            )


        # ----------------------------------------------------
        # UPDATE HISTORY
        #
        # Only absorb the whole current page if:
        # - there were no new products, OR
        # - notification succeeded.
        #
        # If Discord failed, do NOT mark those products
        # as already seen.
        # ----------------------------------------------------

        if new_arrivals_success:

            ever_seen_ids.update(
                current_ids
            )

            ever_seen_handles.update(
                current_handles
            )


    # --------------------------------------------------------
    # SAVE NEW ARRIVAL HISTORY
    # --------------------------------------------------------

    state[
        "new_arrivals_ever_seen"
    ] = sorted(
        ever_seen_ids
    )

    state[
        "new_arrivals_ever_seen_handles"
    ] = sorted(
        ever_seen_handles
    )


    # Current page is for reference only.
    state[
        "new_arrivals_products"
    ] = sorted(
        current_ids
    )

    state[
        "new_arrivals_handles"
    ] = sorted(
        current_handles
    )


except Exception as e:

    print(
        "ERROR checking "
        "New Arrivals: "
        f"{type(e).__name__}: "
        f"{e}"
    )

    check_errors.append(f"New Arrivals: {type(e).__name__}")
    print(
        "Keeping existing "
        "New Arrivals history."
    )


# ============================================================
# SAVE STATE LOCALLY
# ============================================================

state["last_check_at"] = check_started_at
state["workflow_run_id"] = os.environ.get("GITHUB_RUN_ID")
state["workflow_event"] = os.environ.get("GITHUB_EVENT_NAME")
state["check_errors"] = check_errors
if not check_errors:
    state["last_complete_check_at"] = datetime.now(timezone.utc).isoformat()

temp_state_file = (
    STATE_FILE + ".tmp"
)


with open(
    temp_state_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        state,
        f,
        indent=2,
        ensure_ascii=False
    )

    f.write("\n")


os.replace(
    temp_state_file,
    STATE_FILE
)


print("")
print(
    "State saved successfully."
)

if check_errors:
    raise RuntimeError("; ".join(check_errors))
