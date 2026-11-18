# Daily TV Playlist Script — Spec

## Purpose

The script creates and manages a daily Plex playlist. For each show on the roster, in roster order, it adds the next unwatched episodes (`EPISODES_PER_SHOW`, default 2). It ends with one random unwatched movie. A cron job rebuilds the playlist every day.

Progress comes from Plex's watched status. The next day continues where you stopped, and episodes left unwatched are offered again.

## Running

- The script runs with `uv run --with plexapi daily_tv.py <command>`.
- It doesn't need pip or a virtual environment.

## Config

The config is stored in a config file, so the roster and settings survive between runs and cron can read them.

### Defaults

```
PLEX_URL = "http://localhost:32400"
PLAYLIST_NAME = "Daily TV"
MOVIE_SECTION = "Movies"
TV_SECTION = "TV Shows"
EPISODES_PER_SHOW = 2
UPDATE_TIME = "05:00"
```

### Roster

- **TV roster:** `SHOWS`, an ordered list of show titles from `TV_SECTION`.
- **Movie roster:** every unwatched movie in `MOVIE_SECTION`. There is no movie list in the config.
  - A watched movie is out of the roster. An unwatched movie is in.
  - Watching a movie removes it from the roster, the same as `remove-movie`.

### Show file

Shows can be loaded from a plain text file with one show title per line. CSV isn't used because titles can contain commas.

```
# shows.txt
The Office (US)
Seinfeld
Futurama
```

- Shows are taken in file order.
- Blank lines and lines starting with `#` are skipped.
- Titles must match Plex exactly as shown in the library.

### Plex token

- The token is never part of the script's defaults.
- It is read from the `PLEX_API_TOKEN` env var. If that isn't set, `init` asks for it.
- Cron doesn't see shell exports, so `init` saves the token to the config file with owner-only permissions (600).
- If you don't have the token, run this on the Plex server:
  ```
  sudo grep -o 'PlexOnlineToken="[^"]*"' "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"
  ```

## Commands

### `init [--file shows.txt]`

1. Gets the token from `PLEX_API_TOKEN`, or asks for it.
2. Asks for each config value, showing the default. Pressing Enter keeps the default.
3. Sets the TV roster: from `--file` if given, otherwise by asking for show titles in order.
4. Marks all episodes of the roster shows as unwatched. Shows that aren't on the roster are not touched.
5. Marks all movies in `MOVIE_SECTION` as unwatched, so the movie roster starts as the full library.
6. Installs the daily cron job at `UPDATE_TIME`, using the full path to `uv`. Any earlier cron entry from this script is replaced, never duplicated.
7. Runs `update` to build the first playlist.

### `update`

This is what cron runs. It rebuilds the playlist from the config:

1. Deletes the existing playlist named `PLAYLIST_NAME`.
2. For each show in `SHOWS`, in order, adds the next `EPISODES_PER_SHOW` unwatched episodes in season/episode order.
   - A show with no unwatched episodes left is skipped.
3. Adds one random unwatched movie from `MOVIE_SECTION`.
   - If no unwatched movies remain, the playlist is built without a movie and the script reports it.
4. Creates the playlist and prints its contents.

The show commands below take one or more titles, a `--file`, or both. For example:

```
add-show "Seinfeld"
add-show "Seinfeld" "Futurama"
add-show --file shows.txt
```

Each command reports and skips titles it can't use, applies the rest, and rebuilds the playlist once at the end.

### `add-show <title>... [--file shows.txt]`

1. Checks that each show exists in `TV_SECTION`.
2. Adds each one to the end of `SHOWS`, in the order given. Shows already on the roster are skipped.
3. Marks all episodes of each added show as unwatched, so it starts from S01E01.
4. Runs `update`.

### `remove-show <title>... [--file shows.txt]`

1. Removes each show from `SHOWS`. Watched status is not changed.
2. Runs `update`.

### `set-shows <title>... [--file shows.txt]`

1. Replaces `SHOWS` with the given shows, in the order given.
2. Shows that were already on the roster keep their progress.
3. Shows new to the roster are marked unwatched, so they start from S01E01.
4. Shows left out are removed. Their watched status is not changed.
5. If none of the given shows are found, the roster is not changed.
6. Runs `update`.

### `add-movie <title>`

1. Checks that the movie exists in `MOVIE_SECTION`.
2. Marks it as unwatched, which puts it in the roster.
3. Runs `update`.

### `remove-movie <title>`

1. Checks that the movie exists in `MOVIE_SECTION`.
2. Marks it as watched, which takes it out of the roster.
3. Runs `update`.

### `list`

Prints:
- the config, without the token
- the TV roster
- the number of movies in the movie roster
- today's playlist

### `stop`

1. Removes the cron job.
2. Deletes the playlist.

The config file is kept. Run `init` to start again.

## Errors

- A movie title that isn't found in `MOVIE_SECTION` is reported, and nothing is changed.
- A show title that isn't found in `TV_SECTION`, or isn't on the roster for `remove-show`, is reported and skipped. The other shows are still applied.
- A missing show file stops the script with a clear message.
- A missing token stops the script with a clear message.

## Known limitations

- Plex can't tell "removed" apart from "watched" for movies. Re-running `init` resets all movies, which brings back the ones you removed.
- Re-running `init` also resets the watched status of every roster show to the beginning.
