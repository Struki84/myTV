#!/usr/bin/env python3
"""Create and manage a daily Plex TV playlist: next N unwatched episodes per roster show, then one random unwatched movie."""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer

CONFIG_DIR = os.path.expanduser("~/.config/daily-tv")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "update.log")
CRON_MARKER = "# daily-tv"
TOKEN_ENV_VAR = "PLEX_API_TOKEN"

DEFAULTS = {
    "PLEX_URL": "http://localhost:32400",
    "PLAYLIST_NAME": "Daily TV",
    "MOVIE_SECTION": "Movies",
    "TV_SECTION": "TV Shows",
    "EPISODES_PER_SHOW": 2,
    "UPDATE_TIME": "05:00",
}


# ---------- config ----------

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as config_file:
        return json.load(config_file)


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as config_file:
        json.dump(config, config_file, indent=2)
    os.chmod(CONFIG_PATH, 0o600)


def require_config():
    config = load_config()
    if config is None:
        sys.exit(f"No config found at {CONFIG_PATH}. Run 'init' first.")
    return config


def resolve_token(config):
    token = os.environ.get(TOKEN_ENV_VAR) or config.get("PLEX_TOKEN")
    if not token:
        sys.exit(f"No Plex token. Set {TOKEN_ENV_VAR} or run 'init'.")
    return token


def connect(config):
    return PlexServer(config["PLEX_URL"], resolve_token(config))


# ---------- prompts ----------

def ask(label, default):
    answer = input(f"{label} [{default}]: ").strip()
    return answer if answer else default


def ask_int(label, default):
    while True:
        answer = ask(label, default)
        try:
            return int(answer)
        except ValueError:
            print("  Please enter a number.")


def ask_time(label, default):
    while True:
        answer = ask(label, default)
        if parse_time(answer):
            return answer
        print("  Please enter time as HH:MM.")


def parse_time(time_text):
    parts = time_text.split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    hour, minute = int(parts[0]), int(parts[1])
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def ask_token(saved_token):
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if env_token:
        print(f"Using Plex token from {TOKEN_ENV_VAR}.")
        return env_token
    while True:
        prompt = "Plex token [saved]: " if saved_token else "Plex token: "
        answer = input(prompt).strip()
        if answer:
            return answer
        if saved_token:
            return saved_token
        print("  A Plex token is required.")


def ask_shows(tv_section, current_shows):
    if current_shows:
        print("Current TV roster: " + ", ".join(current_shows))
        if input("Keep it? [Y/n]: ").strip().lower() in ("", "y", "yes"):
            return current_shows

    print("Enter show titles one per line, in play order. Empty line to finish.")
    shows = []
    while True:
        show_title = input("  Show: ").strip()
        if not show_title:
            break
        try:
            show = tv_section.get(show_title)
        except NotFound:
            print(f"  Not found in '{tv_section.title}': {show_title}")
            continue
        shows.append(show.title)
    return shows


# ---------- plex helpers ----------

def find_show(plex, config, show_title):
    try:
        return plex.library.section(config["TV_SECTION"]).get(show_title)
    except NotFound:
        sys.exit(f"Show not found in '{config['TV_SECTION']}': {show_title}")


def find_movie(plex, config, movie_title):
    try:
        return plex.library.section(config["MOVIE_SECTION"]).get(movie_title)
    except NotFound:
        sys.exit(
            f"Movie not found in '{config['MOVIE_SECTION']}': {movie_title}")


def find_playlist(plex, config):
    try:
        return plex.playlist(config["PLAYLIST_NAME"])
    except NotFound:
        return None


def describe_item(item):
    if item.type == "movie":
        return f"[movie] {item.title}"
    return f"{item.grandparentTitle} {item.seasonEpisode.upper()} {item.title}"


# ---------- cron ----------

def read_crontab():
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def write_crontab(lines):
    content = "\n".join(lines) + "\n" if lines else ""
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)


def find_uv():
    uv_path = shutil.which("uv")
    if uv_path:
        return uv_path
    fallback_path = os.path.expanduser("~/.local/bin/uv")
    if os.path.exists(fallback_path):
        return fallback_path
    sys.exit("Could not find 'uv'. Install it first.")


def install_cron(config):
    hour, minute = parse_time(config["UPDATE_TIME"])
    script_path = os.path.abspath(__file__)
    cron_line = (
        f"{minute} {hour} * * * {find_uv()} run --with plexapi {script_path} update "
        f">> {LOG_PATH} 2>&1 {CRON_MARKER}"
    )
    lines = [line for line in read_crontab() if CRON_MARKER not in line]
    lines.append(cron_line)
    write_crontab(lines)
    print(f"Cron job installed: daily at {config['UPDATE_TIME']}.")


def remove_cron():
    lines = read_crontab()
    kept_lines = [line for line in lines if CRON_MARKER not in line]
    if len(kept_lines) == len(lines):
        print("No cron job found.")
        return
    write_crontab(kept_lines)
    print("Cron job removed.")


# ---------- commands ----------

def cmd_init(args):
    config = load_config() or dict(DEFAULTS, SHOWS=[])

    token = ask_token(config.get("PLEX_TOKEN"))
    config["PLEX_URL"] = ask("Plex URL", config.get(
        "PLEX_URL", DEFAULTS["PLEX_URL"]))
    config["PLAYLIST_NAME"] = ask("Playlist name", config.get(
        "PLAYLIST_NAME", DEFAULTS["PLAYLIST_NAME"]))
    config["MOVIE_SECTION"] = ask("Movie library", config.get(
        "MOVIE_SECTION", DEFAULTS["MOVIE_SECTION"]))
    config["TV_SECTION"] = ask("TV library", config.get(
        "TV_SECTION", DEFAULTS["TV_SECTION"]))
    config["EPISODES_PER_SHOW"] = ask_int("Episodes per show", config.get(
        "EPISODES_PER_SHOW", DEFAULTS["EPISODES_PER_SHOW"]))
    config["UPDATE_TIME"] = ask_time("Daily update time (HH:MM)", config.get(
        "UPDATE_TIME", DEFAULTS["UPDATE_TIME"]))

    plex = PlexServer(config["PLEX_URL"], token)
    tv_section = plex.library.section(config["TV_SECTION"])
    movie_section = plex.library.section(config["MOVIE_SECTION"])

    config["SHOWS"] = ask_shows(tv_section, config.get("SHOWS", []))
    config["PLEX_TOKEN"] = token
    save_config(config)
    print(f"Config saved to {CONFIG_PATH}.")

    print("Resetting watched status of roster shows...")
    for show_title in config["SHOWS"]:
        tv_section.get(show_title).markUnwatched()
        print(f"  {show_title}")

    print("Resetting watched status of all movies...")
    reset_count = 0
    for movie in movie_section.all():
        if movie.isWatched:
            movie.markUnwatched()
            reset_count += 1
    print(f"  {reset_count} movies marked unwatched.")

    install_cron(config)
    cmd_update(args)


def cmd_update(args):
    config = require_config()
    plex = connect(config)
    tv_section = plex.library.section(config["TV_SECTION"])
    movie_section = plex.library.section(config["MOVIE_SECTION"])

    existing_playlist = find_playlist(plex, config)
    if existing_playlist:
        existing_playlist.delete()

    items = []
    for show_title in config["SHOWS"]:
        try:
            show = tv_section.get(show_title)
        except NotFound:
            print(f"Skipping (not found): {show_title}")
            continue
        next_episodes = show.unwatched()[: config["EPISODES_PER_SHOW"]]
        if not next_episodes:
            print(f"Skipping (no unwatched episodes): {show_title}")
            continue
        items.extend(next_episodes)

    unwatched_movies = movie_section.search(unwatched=True)
    if unwatched_movies:
        items.append(random.choice(unwatched_movies))
    else:
        print("No unwatched movies left: playlist built without a movie.")

    if not items:
        print("Nothing to add: playlist not created.")
        return

    plex.createPlaylist(config["PLAYLIST_NAME"], items=items)
    print(f"Playlist '{config['PLAYLIST_NAME']}':")
    for item in items:
        print(f"  {describe_item(item)}")


def cmd_add_show(args):
    config = require_config()
    plex = connect(config)
    show = find_show(plex, config, args.title)
    if show.title in config["SHOWS"]:
        sys.exit(f"Already on the roster: {show.title}")
    config["SHOWS"].append(show.title)
    save_config(config)
    show.markUnwatched()
    print(f"Added: {show.title} (starts from S01E01)")
    cmd_update(args)


def cmd_remove_show(args):
    config = require_config()
    matching_titles = [show_title for show_title in config["SHOWS"]
                       if show_title.lower() == args.title.lower()]
    if not matching_titles:
        sys.exit(f"Not on the roster: {args.title}")
    config["SHOWS"].remove(matching_titles[0])
    save_config(config)
    print(f"Removed: {matching_titles[0]}")
    cmd_update(args)


def cmd_add_movie(args):
    config = require_config()
    plex = connect(config)
    movie = find_movie(plex, config, args.title)
    movie.markUnwatched()
    print(f"Added to movie roster: {movie.title}")
    cmd_update(args)


def cmd_remove_movie(args):
    config = require_config()
    plex = connect(config)
    movie = find_movie(plex, config, args.title)
    movie.markWatched()
    print(f"Removed from movie roster: {movie.title}")
    cmd_update(args)


def cmd_list(args):
    config = require_config()
    plex = connect(config)

    print("Config:")
    for key, value in config.items():
        if key in ("PLEX_TOKEN", "SHOWS"):
            continue
        print(f"  {key} = {value}")

    print("TV roster:")
    for show_title in config["SHOWS"]:
        print(f"  {show_title}")

    movie_count = len(plex.library.section(
        config["MOVIE_SECTION"]).search(unwatched=True))
    print(f"Movie roster: {movie_count} unwatched movies")

    playlist = find_playlist(plex, config)
    if playlist is None:
        print("Today's playlist: none")
        return
    print(f"Today's playlist '{playlist.title}':")
    for item in playlist.items():
        print(f"  {describe_item(item)}")


def cmd_stop(args):
    config = require_config()
    remove_cron()
    plex = connect(config)
    playlist = find_playlist(plex, config)
    if playlist:
        playlist.delete()
        print(f"Playlist deleted: {config['PLAYLIST_NAME']}")
    else:
        print("No playlist found.")


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser(description="Daily Plex TV playlist")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "init", help="configure, reset watched status, install cron, build playlist")
    subparsers.add_parser("update", help="rebuild the playlist (run by cron)")
    subparsers.add_parser(
        "list", help="show config, roster and today's playlist")
    subparsers.add_parser("stop", help="remove cron job and delete playlist")

    for command_name, help_text in (
        ("add-show", "add a show to the roster, starting from S01E01"),
        ("remove-show", "remove a show from the roster"),
        ("add-movie", "mark a movie unwatched (into the roster)"),
        ("remove-movie", "mark a movie watched (out of the roster)"),
    ):
        command_parser = subparsers.add_parser(command_name, help=help_text)
        command_parser.add_argument("title")

    commands = {
        "init": cmd_init,
        "update": cmd_update,
        "add-show": cmd_add_show,
        "remove-show": cmd_remove_show,
        "add-movie": cmd_add_movie,
        "remove-movie": cmd_remove_movie,
        "list": cmd_list,
        "stop": cmd_stop,
    }

    args = parser.parse_args()
    commands[args.command](args)


if __name__ == "__main__":
    main()
