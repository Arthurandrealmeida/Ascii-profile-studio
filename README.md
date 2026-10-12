# Ascii-profile-studio
A customizable GitHub Profile README generator that turns your photos into detailed ASCII art portraits. Create terminal-style SVG profiles with editable layouts, themes, custom fields, and GitHub stats.


# ASCII Profile Studio

**Turn your photos into ASCII art and build a fully customizable GitHub Profile README.**

ASCII Profile Studio is a free, open-source **GitHub Profile README generator** and **photo-to-ASCII art converter** that lets you create personalized, terminal-style GitHub profiles.

Inspired by classic terminal interfaces and Neofetch-style system information displays, it combines a detailed ASCII portrait with customizable profile information, programming languages, interests, social links, and optional GitHub statistics.

Everything runs locally on your computer. No account, cloud processing, or generative AI is required.

## Preview

![ASCII Profile Studio Preview](output/preview.png)

*Example of a GitHub README profile generated with ASCII Profile Studio.*

## Features

### Photo to ASCII Art

Convert your own photo into a detailed ASCII portrait.

- High-resolution ASCII portrait generation
- Multiple conversion algorithms
- Adjustable contrast, brightness, and sharpness
- Interactive image cropping and zoom
- Custom character sets and character sizes
- Export your ASCII portrait separately as SVG
- No AI-generated faces or embedded raster images in the ASCII SVG

### GitHub Profile README Generator

Create a personalized GitHub profile in the style of a terminal or Neofetch display.

- Add, remove, rename, and reorder fields
- Create custom sections for skills, projects, hobbies, and more
- Customize typography, spacing, margins, and columns
- Drag-and-drop section and field ordering
- Undo and redo changes
- Live preview while editing

You are not limited to predefined fields. Replace `Uptime` with `Projects`, `Currently Learning`, `Focus`, or anything else.

### Themes and Visual Presets

Choose from four built-in presets:

- Classic Terminal
- Compact
- Neon
- Minimalist

Customize colors for both dark and light themes, including labels, values, backgrounds, and highlighted text.

### SVG Export

Export scalable profile graphics that can be embedded directly in your GitHub README.

- Dark and light SVG versions
- Standalone ASCII portrait SVG
- Editable text-based SVG output
- Downloads reflecting your current changes
- No external fonts or remote image dependencies

### GitHub Statistics

Optionally connect your public GitHub username to display:

- Public repositories
- Followers
- Stars received on eligible repositories
- Forks of eligible repositories

GitHub statistics can be refreshed manually or through an optional GitHub Actions workflow.

Statistics that cannot be retrieved reliably are displayed as unavailable rather than estimated.

## Getting Started

### Requirements

- Python 3
- A modern web browser
- Git, if you want to clone the repository

### Linux / Fedora

Clone the repository:

```bash
git clone https://github.com/Arthurandrealmeida/ascii-profile-studio.git
cd ascii-profile-studio
```

Run:

```bash
./iniciar-fedora.sh
```

Open the editor at:

```text
http://127.0.0.1:8765
```

### Manual Installation — Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

### Windows

Open PowerShell in the project directory:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then visit `http://127.0.0.1:8765`.

## How to Create Your ASCII GitHub Profile

1. **Upload your photo.** Choose a clear portrait in PNG, JPG, or WebP format.
2. **Generate your ASCII art.** Select the detailed portrait mode or try one of the classic conversion algorithms.
3. **Adjust your portrait.** Fine-tune cropping, zoom, resolution, contrast, and character size.
4. **Customize your profile.** Add programming languages, operating systems, projects, hobbies, links, or any other information.
5. **Choose your appearance.** Select a preset or customize the layout and colors.
6. **Export your profile.** Download your GitHub-ready SVG files.
7. **Add it to your GitHub README.** Embed the exported graphic in your profile repository.

## Customize Every Field

Unlike fixed GitHub README templates, ASCII Profile Studio lets you edit your profile content freely.

For example:

```yaml
sections:
  - title: About
    rows:
      - label: OS
        value: Fedora Linux
      - label: IDE
        value: VSCode, Neovim
      - label: Focus
        value: Full-Stack Development, AI

  - title: Languages
    rows:
      - label: Programming
        value: Python, JavaScript, C++
      - label: Learning
        value: Rust
```

You can edit these fields in the graphical interface without manually editing YAML.

## Add Your Profile to GitHub

GitHub supports special profile repositories.

1. Create a public repository with exactly the same name as your GitHub username.
2. Add a `README.md` file to that repository.
3. Copy the exported SVG files into an `output/` folder.
4. Reference the SVG files in your README.

For example:

```html
<picture>
  <source
    media="(prefers-color-scheme: dark)"
    srcset="output/dark_mode.svg"
  />
  <source
    media="(prefers-color-scheme: light)"
    srcset="output/light_mode.svg"
  />
  <img
    alt="My ASCII GitHub Profile"
    src="output/dark_mode.svg"
  />
</picture>
```

Your GitHub profile can now display a personalized ASCII portrait and terminal-style information panel.

## Automatic GitHub Stats

ASCII Profile Studio can retrieve supported public GitHub statistics.

An optional GitHub Actions workflow can regenerate your SVG files on a schedule.

To enable it:

1. Configure your GitHub username in the editor.
2. Enable automatic statistics updates.
3. Save and generate the SVG files.
4. Publish the workflow in a repository with GitHub Actions enabled.

The included workflow updates the SVG files in its own repository. Publishing them to a separate profile repository requires additional configuration.

## Privacy First

ASCII Profile Studio is designed to run locally.

- Your uploaded photos are processed on your computer.
- No generative AI service is used.
- No account is required.
- Profile generation works offline.
- GitHub API access is optional and used for public statistics.

**Important:** If you publish the entire project directory, your photos and configuration files may also become public. Remove personal files and private information before pushing the project to GitHub.

The local editor is not intended to be exposed as a public web service.

## Project Structure

```text
ascii-profile-studio/
├── app.py
├── generator.py
├── github_stats.py
├── config.yaml
├── static/
├── assets/
├── output/
├── tests/
├── .github/workflows/
└── README_PROFILE_TEMPLATE.md
```

## Run Tests

```bash
python -m unittest discover -s tests -v
```

## Who Is This For?

ASCII Profile Studio is designed for:

- Developers who want a unique GitHub profile README
- People looking for a customizable README generator
- Users who want to convert a portrait photo into ASCII art
- Fans of terminal aesthetics, Neofetch, and CLI-style profiles
- Developers who prefer SVG-based profile graphics
- Anyone who wants more control than traditional GitHub README templates provide

## Related Keywords

GitHub Profile README Generator · ASCII Art Generator · Photo to ASCII Converter · Neofetch GitHub Profile · Terminal Style README · SVG Profile Generator · Custom GitHub README · ASCII Portrait Generator · Developer Profile Generator

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

**ASCII Profile Studio — Make your GitHub profile look like your own terminal.**
