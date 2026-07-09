# Restaurant Digital TV Menu System

A local MVP for managing restaurant menu content from a laptop and displaying different menu layouts on one or more TVs.

Admins can manage multiple restaurant locations from the same dashboard. Each location has its own categories, menu items, TV screens, and display URLs.

## Run Locally

```bash
python3 server.py
```

Then open:

```text
http://127.0.0.1:4173
```

Example TV display URLs:

```text
http://127.0.0.1:4173/display/main-tv
http://127.0.0.1:4173/display/drinks-tv
http://127.0.0.1:4173/display/uptown-main-tv
```

## Included MVP Features

- Admin dashboard with menu, category, and TV counts
- Multi-location admin access with a location switcher
- Location CRUD with name, address, and phone
- Menu item CRUD with price, category, image URL, sort order, and stock status
- Category CRUD with sort order
- Multi-TV screen profiles with unique slugs
- Category assignment per TV
- Optional item pinning per TV
- Per-TV design settings for colors, font sizes, restaurant name, and image/sold-out visibility
- Admin preview that uses the same renderer as the TV display
- Customer-facing fullscreen TV route at `/display/:slug`
- Automatic polling refresh on TV display pages

## Notes

The original requested production stack is React, Vite, Express, and Supabase. This workspace did not include those dependencies, so this MVP uses the existing no-install pattern:

- Frontend: browser JavaScript, HTML, CSS
- Backend: Python standard library HTTP server
- Database: SQLite

The API shape mirrors the requested REST endpoints so it can be moved to Express/Supabase later with minimal frontend changes.
