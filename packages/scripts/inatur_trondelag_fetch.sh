#!/bin/bash
# Fetch all iNatur Trøndelag småvilt offers with pagination
# Filters out blacklisted municipalities and innenbygds offers
# Compares with previously seen offers to detect new/updated ones

STORAGE_FILE="/config/.storage/inatur_trondelag_seen.json"
TEMP_FILE="/tmp/inatur_trondelag_current.json"

# Blacklisted municipalities
BLACKLIST="Grong|Lierne|Namdalseid|Namsos|Namsskogan|Nærøysund|Røyrvik|Rosse|Snåsa"

# URL-encoded search filter for lirype in Trøndelag småvilttilbud
SEARCH_FILTER='%5B%7B%22felt%22%3A%22arter%22%2C%22sokeord%22%3A%22lirype%22%7D%2C%7B%22felt%22%3A%22fylker%22%2C%22sokeord%22%3A%22Tr%C3%B8ndelag%22%7D%2C%7B%22felt%22%3A%22type%22%2C%22sokeord%22%3A%22smaavilttilbud%22%7D%5D'
BASE_URL="https://www.inatur.no/internal/search"

# Initialize storage if it doesn't exist
if [ ! -f "$STORAGE_FILE" ]; then
    echo '{"offers":{}}' > "$STORAGE_FILE"
fi

# Fetch first page only (API sorts by sistOppdatert desc, so new/updated offers appear first)
url="${BASE_URL}?f=${SEARCH_FILTER}&ledig=true&p=0"
response=$(curl -s "$url")

if [ -z "$response" ]; then
    echo '{"error":"Failed to fetch page 0"}' >&2
    exit 1
fi

all_offers=$(echo "$response" | jq '.resultat // []')

# # Fetch all pages (commented out - revert if single page isn't enough)
# all_offers="[]"
# page=0
# total_pages=1
# 
# while [ $page -lt $total_pages ]; do
#     url="${BASE_URL}?f=${SEARCH_FILTER}&ledig=true&p=${page}"
#     response=$(curl -s "$url")
#     
#     if [ -z "$response" ]; then
#         echo '{"error":"Failed to fetch page '$page'"}' >&2
#         break
#     fi
#     
#     # Get pagination info
#     total_pages=$(echo "$response" | jq -r '.paginering.totaltAntallSider // 1')
#     
#     # Extract results and append
#     page_offers=$(echo "$response" | jq '.resultat // []')
#     all_offers=$(echo "$all_offers" "$page_offers" | jq -s 'add')
#     
#     page=$((page + 1))
# done

# Filter offers:
# 1. Remove blacklisted municipalities
# 2. Remove innenbygds offers
filtered_offers=$(echo "$all_offers" | jq --arg blacklist "$BLACKLIST" '
    [.[] | 
        select(
            (.kommuner | map(test($blacklist; "i")) | any | not) and
            (.tittel | test("innenbygds"; "i") | not)
        )
    ]
')

# Load previously seen offers
seen_offers=$(cat "$STORAGE_FILE" | jq '.offers // {}')

# Find new or updated offers
new_or_updated=$(echo "$filtered_offers" | jq --argjson seen "$seen_offers" '
    [.[] |
        . as $offer |
        ($offer.sistOppdatert // 0) as $updated |
        ($offer.sistPublisert // 0) as $published |
        (if $updated > 2000000000 then $updated / 1000 else $updated end) as $updated_sec |
        (if $published > 2000000000 then $published / 1000 else $published end) as $published_sec |
        ([$updated_sec, $published_sec] | max) as $latest |
        ($seen[$offer.id].last_update // 0) as $prev_update |
        if ($seen[$offer.id] == null) then
            {
                id: $offer.id,
                tittel: $offer.tittel,
                kommuner: $offer.kommuner,
                url: $offer.url,
                sistOppdatertFormatert: $offer.sistOppdatertFormatert,
                is_new: true
            }
        elif ($latest > $prev_update) then
            {
                id: $offer.id,
                tittel: $offer.tittel,
                kommuner: $offer.kommuner,
                url: $offer.url,
                sistOppdatertFormatert: $offer.sistOppdatertFormatert,
                is_new: false
            }
        else
            empty
        end
    ]
')

# Build current offers map for storage
current_offers=$(echo "$filtered_offers" | jq '
    reduce .[] as $offer ({};
        ($offer.sistOppdatert // 0) as $updated |
        ($offer.sistPublisert // 0) as $published |
        (if $updated > 2000000000 then $updated / 1000 else $updated end) as $updated_sec |
        (if $published > 2000000000 then $published / 1000 else $published end) as $published_sec |
        ([$updated_sec, $published_sec] | max) as $latest |
        . + {($offer.id): {last_update: $latest, tittel: $offer.tittel}}
    )
')

# Save current state
echo "{\"offers\": $current_offers, \"last_check\": \"$(date -Iseconds)\"}" > "$STORAGE_FILE"

# Output result
total_filtered=$(echo "$filtered_offers" | jq 'length')
new_count=$(echo "$new_or_updated" | jq 'length')

echo "{\"new_or_updated\": $new_or_updated, \"total_filtered\": $total_filtered, \"new_count\": $new_count, \"last_check\": \"$(date -Iseconds)\"}"
