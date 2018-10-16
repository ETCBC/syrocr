OCR of Syriac text
==================

The package `syrocr` provides an interface to several Python modules
aimed at optical recognition of Syriac text, in a manually supervised
automated workflow.

`syrocr` was designed for the digitization of a specific printed Syriac
text, but might be useful for the optical recognition for other, similar,
texts.

The intended workflow consists of a number of steps, outlined below.

Installation
------------

- Clone the `syrocr` repository
- In the root directory of the repository: `$ pip3 install .`

This makes the modules of the package available system-wide, so they can
be imported in Python interactive mode:

    >>> import syrocr
    >>> from syrocr import getlines

The package also provides a script that can be run from the command line:
`syrocr.py`, which is found in the package's root directory. This command
line interface is used in the workflow described below. It can be accessed
as an argument to the `python3` command:

    $ python3 <path>/syrocr.py <subcommand> ...

It is more convenient to make the script executable, and make it available
system-wide by adding a softlink to it in a directory in your PATH
(e.g. `~/bin`):

    $ chmod +x syrocr.py
    $ ln -s ln -s ~/path/to/syrocr/syrocr.py ~/bin/syrocr

The program should then be accessible from anywhere on the system on the
command line:

    $ syrocr --help
    usage: syrocr [-h] <subcommand> ...

    optional arguments:
      -h, --help    show this help message and exit

    subcommands:
      <subcommand>  subcommand description:
        getlines    Get lines from source image
        drawboxes   Draw boxes around lines on source image
        getchars    Recognize individual characters

    For help on subcommands, see: syrocr <subcommand> -h

Preparation of the images
-------------------------

The text to be recognized must be presented in clean, straight images.
A good tool for the preprocessing of scanned images is
[ScanTailor](http://scantailor.org/).

Recognition of text lines
-------------------------

The first step of recognition is the recognition of text lines.
Once the page is divided into lines, the lines can be processed to
recognize the individual characters on the line.

To recognize the text lines in the image `source_image.tif`,
the subcommand `getlines` is used as follows:

    $ syrocr getlines source_image.tif

This creates two new files:
- a JSON file, called `source_image_lines.json`, containing the line
  coordinates and line types,
- and a PNG image called `source_image_lines.json`, in which the recognized
  lines are indicated by coloured boxes.

To process all images in the current directory, use a `for` loop:

    $ for file in *; do echo $file; syrocr getlines $file; done

Manual inspection of text line recognition
------------------------------------------

The PNG images make it possible to quickly review the results of the
line recognition step. If an error is found, it can be relatively
easily corrected by editing the generated JSON file.

To see if the changes have the desired effect, the PNG image can be
updated with the following command:

    $ syrocr drawboxes source_image.tif source_image_lines.json

Recognition of characters
-------------------------

The next step is character recognition with the subcommand `getchars`.
This uses the source image and the JSON lines file as input. A third
file, a JSON file with `tables`, contains the character tables with
the recognized character images, which are used as a reference to
compare new character images against. On every run of this step, the
tables are updated with the newly found characters.

    $ syrocr getchars source_image.tif source_image_lines.json tables.json

The recognized characters per line are stored in an additional JSON file,
called `source_image_textlines.json`. This contains per character the
id of the character in the JSON tables, the distance to the previous
character, and the position on the page.

Manual assignment of characters
-------------------------------

The recognized characters are stored in the `tables.json` file, but are
not assigned a value, since all the program can do is compare recognized
characters with each other. The next step is to assign a value to all
recognized characters. The easiest way to do this is in a Jupyter Notebook,
with an interactive script showing the image of the recognized character
as well as the image of the line in which it occurs to provide context,
after which the user is prompted to provide the proper value, the script
(syriac, roman, cursive, etc), and optionally a word distance value.
A Jupyter Notebook is provided in the root directory of the `syrocr` package,
named `UpdateTables.ipynb`.

When all relevant entries have a value assigned to it, the updated tables
can be written to `tables.json` and used to generate the recognized text.
