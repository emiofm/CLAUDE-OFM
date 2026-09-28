"""What the official Threads API does and does not provide (shown in the UI)."""

AVAILABLE = [
    {
        "metric": "Public posts matching a keyword or topic tag",
        "endpoint": "GET /keyword_search",
        "permission": "threads_keyword_search",
        "notes": "Before App Review approval, only the authenticated user's own posts are searchable. "
        "Meta limits keyword search to 2,200 queries per user per rolling 24h.",
    },
    {
        "metric": "Post text, permalink, timestamp, media type, media/thumbnail URL, username, has_replies",
        "endpoint": "GET /keyword_search, GET /profile_posts",
        "permission": "threads_keyword_search / threads_profile_discovery",
        "notes": "Fields requested explicitly via the fields parameter.",
    },
    {
        "metric": "Public profile: name, bio, profile picture, verified flag",
        "endpoint": "GET /profile_lookup?username=",
        "permission": "threads_profile_discovery",
        "notes": "Exact username only; only profiles Meta makes discoverable are returned.",
    },
    {
        "metric": "Follower count and profile-level likes/replies/reposts/quotes/views counts",
        "endpoint": "GET /profile_lookup?username=",
        "permission": "threads_profile_discovery",
        "notes": "Returned only when Meta includes them for that profile; otherwise shown as unavailable.",
    },
    {
        "metric": "Recent public posts of a profile (used for 7/30/90-day activity)",
        "endpoint": "GET /profile_posts?username=",
        "permission": "threads_profile_discovery",
        "notes": "Paginated with cursors; without this permission activity is a lower bound from search hits.",
    },
]

UNAVAILABLE = [
    {
        "metric": "Follower / following lists of third-party accounts",
        "notes": "No official endpoint exists.",
    },
    {
        "metric": "Per-post like / reply / repost counts for other people's posts",
        "notes": "Media insights are only available for the authenticated user's own media "
        "(threads_manage_insights). Stored as NULL.",
    },
    {
        "metric": "Follower count when profile_lookup is not permitted or omits it",
        "notes": "Shown as 'Follower count unavailable from official Threads API'. Never estimated.",
    },
    {
        "metric": "Searching users/profiles by keyword, or by visual appearance",
        "notes": "Only posts are searchable; profile_lookup needs an exact username.",
    },
    {
        "metric": "Links in bio / external monetisation platforms",
        "notes": "Only inferred as a *possible* signal from bio and post text.",
    },
]
