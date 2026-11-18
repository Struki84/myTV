# Daily TV

Turn your Plex library into a daily TV programme. Every day the script builds a playlist with the next unwatched episodes of each show on your roster, followed by one random unwatched movie.

## How it works

- **Progress is Plex's watched status.** For each show, the script picks the next *unwatched* episodes in season/episode order. When you watch them, the next day's playlist moves on. Anything you don't watch is offered again.
- **Shows play in roster order**, and the movie always comes last.
- **The movie pool is every unwatched movie** in your movie library. Watching a movie takes it out of the pool. `remove-movie` does the same by marking it watched, and `add-movie` puts it back by marking it unwatched.
- **A cron job runs `update` once a day.** Each run deletes the playlist and builds a new one.
- **Settings and the TV roster** are stored in `~/.config/daily-tv/config.json`, with owner-only permissions because the file holds the Plex token. Each daily run logs to `~/.config/daily-tv/update.log`.

## Requirements

- Python 3
- [python-plexapi](https://github.com/pkkid/python-plexapi)
- A Plex Media Server and a Plex token
- `cron` (Linux or macOS)

## Installation

Install the dependency:

```
pip install plexapi
```

Or skip installing it and run the script with [uv](https://docs.astral.sh/uv/), which fetches `plexapi` for each run. This is handy on systems that block a system-wide `pip install`, such as recent Ubuntu and Debian:

```
uv run --with plexapi daily_tv.py <command>
```

## Quick start

```
export PLEX_API_TOKEN="your-token"
python3 daily_tv.py init --file shows.txt
```

```
uv run --with plexapi daily_tv.py init --file shows.txt
```

## Commands

### `init`

Sets everything up. Run it once at the start, or again to reconfigure.

```
python3 daily_tv.py init
python3 daily_tv.py init --file shows.txt
```

```
uv run --with plexapi daily_tv.py init
uv run --with plexapi daily_tv.py init --file shows.txt
```

1. **Gets the Plex token.** It uses `PLEX_API_TOKEN` if that is set, otherwise it asks for the token.
2. **Asks for the settings.** It shows the default (or the current value) for each one, and pressing Enter keeps it:

   | Setting | Default |
   |---|---|
   | Plex URL | `http://localhost:32400` |
   | Playlist name | `Daily TV` |
   | Movie library | `Movies` |
   | TV library | `TV Shows` |
   | Episodes per show | `2` |
   | Daily update time | `05:00` (24h, server local time) |

3. **Sets the TV roster.** It reads `--file` if given, otherwise it asks for show titles one by one.
4. **Resets watched status.** Every episode of the roster shows is marked unwatched, so they start from S01E01. Every movie is marked unwatched, so the movie pool is the whole library. Shows that aren't on the roster are left alone.
5. **Installs the cron job** at the update time. Any earlier entry from this script is replaced.
6. **Builds the first playlist.**

> Re-running `init` resets the roster shows to episode 1 and brings back every movie, including ones you removed.

### `update`

Rebuilds the playlist from the config. Cron runs this every day. You rarely need it yourself, because every roster command already rebuilds the playlist.

```
python3 daily_tv.py update
```

```
uv run --with plexapi daily_tv.py update
```

- Shows with no unwatched episodes left are skipped.
- If no unwatched movies remain, the playlist is built without a movie and the script says so.

### `add-show`

Adds one or more shows to the end of the roster.

```
python3 daily_tv.py add-show "Seinfeld"
python3 daily_tv.py add-show "Seinfeld" "Futurama"
python3 daily_tv.py add-show --file shows.txt
```

```
uv run --with plexapi daily_tv.py add-show "Seinfeld"
uv run --with plexapi daily_tv.py add-show "Seinfeld" "Futurama"
uv run --with plexapi daily_tv.py add-show --file shows.txt
```

- Each added show is marked unwatched, so it starts from S01E01.
- Shows already on the roster, and titles not found in Plex, are reported and skipped.
- The playlist is rebuilt once at the end.

### `remove-show`

Removes one or more shows from the roster and rebuilds the playlist.

```
python3 daily_tv.py remove-show "Seinfeld"
python3 daily_tv.py remove-show --file shows.txt
```

```
uv run --with plexapi daily_tv.py remove-show "Seinfeld"
uv run --with plexapi daily_tv.py remove-show --file shows.txt
```

Watched status isn't changed. If you add the show back later, it starts from episode 1 again.

### `set-shows`

Replaces the roster with the given shows, in the given order.

```
python3 daily_tv.py set-shows --file shows.txt
```

```
uv run --with plexapi daily_tv.py set-shows --file shows.txt
```

- Shows that were already on the roster keep their progress.
- New shows start from S01E01.
- Shows you leave out are dropped, and their watched status isn't changed.

Use this after editing your show file. Editing the file by itself changes nothing.

### `add-movie` / `remove-movie`

Puts a movie into the random pool or takes it out.

```
python3 daily_tv.py add-movie "Alien"
python3 daily_tv.py remove-movie "Alien"
```

```
uv run --with plexapi daily_tv.py add-movie "Alien"
uv run --with plexapi daily_tv.py remove-movie "Alien"
```

- `add-movie` marks the movie unwatched, which puts it in the pool.
- `remove-movie` marks it watched, which takes it out.

Both rebuild the playlist.

### `list`

Prints the settings (without the token), the TV roster, how many movies are in the pool, and today's playlist.

```
python3 daily_tv.py list
```

```
uv run --with plexapi daily_tv.py list
```

### `stop`

Removes the cron job and deletes the playlist. The config is kept. Run `init` to start again.

```
python3 daily_tv.py stop
```

```
uv run --with plexapi daily_tv.py stop
```

## Show file

A plain text file with one title per line. Lines are read in order, and blank lines and `#` comments are skipped.

```
# shows.txt
The Office (US)
Seinfeld
Futurama
```

Titles must match Plex exactly as shown in your library.

## Plex token

The token is never stored in the script. It comes from `init`, or from the env var:

```
export PLEX_API_TOKEN="your-token"
```

`init` saves the token to the config file, because cron doesn't see shell exports. If the env var is set, it takes priority over the saved token.

To find your token, see Plex's guide [Finding an authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/). On a Linux server you can also read it directly:

```
sudo grep -o 'PlexOnlineToken="[^"]*"' "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"
```
