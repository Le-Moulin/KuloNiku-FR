# Installation from source

This method is intended for people who want to inspect, modify, or test the
code. For a normal installation, use the
[latest release](https://github.com/Le-Moulin/KuloNiku-FR/releases).

## Requirements

- [Python](https://www.python.org/);
- [uv](https://docs.astral.sh/uv/);
- a legitimate installation of the demo or full game.

## Install

Close the game, then install the dependencies:

```sh
uv sync
```

Run the simulation first. It does not modify any file.

On Windows:

```powershell
uv run kuloniku-fr install "C:\Program Files (x86)\Steam\steamapps\common\KuloNiku"
```

On macOS:

```sh
uv run kuloniku-fr install "/path/to/KuloNiku.app"
```

On Linux or Steam Deck:

```sh
uv run kuloniku-fr install "/path/to/steamapps/common/KuloNiku"
```

On Windows and Linux, the path must point to the folder that contains
`KuloNiku_Data`.

If the diagnosis is correct, run the same command with `--apply`:

```sh
uv run kuloniku-fr install "/path/to/KuloNiku.app" --apply
```

Launch the game from Steam and select **Français** in the settings.

## Restore the game

Run a restoration simulation first:

```sh
uv run kuloniku-fr restore "/path/to/KuloNiku.app"
```

If the diagnosis is correct, add `--apply`:

```sh
uv run kuloniku-fr restore "/path/to/KuloNiku.app" --apply
```

The tool uses the verified backup created during installation.

## Technical details

- [Architecture and compatibility](DISTRIBUTION.md)
- [Updates](UPDATES.md)
- [Security](../SECURITY.md)
