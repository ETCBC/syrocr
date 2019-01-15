OCR of Syriac text
==================

The package `syrocr` provides an interface to several Python modules
aimed at optical recognition of Syriac text, in a manually supervised
automated workflow.

`syrocr` was designed for the digitization of a specific printed Syriac
text, but might be useful for the optical recognition for other, similar,
texts.

The intended workflow consists of a number of steps, outlined below.

**Warning: This code is under development so as yet not everything works
as intended or at all.**

**Instructions below are known to work on Ubuntu Linux in a bash login shell,
but may work in other setups as well.**

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
system-wide by adding a soft link (symlink) to it in a directory in your PATH
(e.g. `~/bin`):

    $ chmod +x syrocr.py
    $ ln -s ln -s ~/path/to/syrocr/syrocr.py ~/bin/syrocr

Instead of the permanent solution with the soft link mentioned above, it is
also possible to create an alias, which will work during the current shell
session (although it can be made permanent by putting it in ~/.bashrc):

    $ alias syrocr='python3 ~/path/to/syrocr/syrocr.py'

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

![mitchell2_test-01](https://user-images.githubusercontent.com/35661854/51177272-cdb10600-18c7-11e9-9135-8c8d97047fab.png)

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

    $ for file in * ; do echo $file; syrocr getlines $file; done

Manual inspection of text line recognition
------------------------------------------

The PNG images make it possible to quickly review the results of the
line recognition step. If an error is found, it can be relatively
easily corrected by editing the generated JSON file.

To see if the changes have the desired effect, the PNG image can be
updated with the following command:

    $ syrocr drawboxes source_image.tif source_image_lines.json

![mitchell2_test-01_lines](https://user-images.githubusercontent.com/35661854/51177089-59766280-18c7-11e9-9dd6-25551afa539f.png)

Recognition of characters
-------------------------

The next step is character recognition with the subcommand `getchars`.
This uses the source image and the JSON lines file as input. A third
file, a JSON file with `tables`, contains the character tables with
the recognized character images, which are used as a reference to
compare new character images against. On every run of this step, the
tables are updated with the newly found characters.

    $ syrocr getchars -v source_img_dir json_lines_dir json_tables_file

The getchars program will look for files ending with `.tif` in the
`source_img_dir`, then for each of those find the corresponding file
ending with `_lines.json` in the `json_lines_dir`, which contains the
line coordinates.

The recognized characters per line are stored in an additional JSON file,
called `source_image_textlines.json`. This contains per character the
id of the character in the JSON tables, the distance to the previous
character, and the position on the page.
If the file exists, it will be updated with the new results.
If it does not exist, it will be created.

The `-v` flag makes the output verbose, showing the number of new characters
after processing each line, and totals after each image/page.

An example, assuming the original images are in the parent directory,
the json files are in the current working directory, and the tables
file is called `tables.json`:

    $ syrocr getchars -v .. . tables.json

Manual assignment of characters
-------------------------------

The recognized characters are stored in the `tables.json` file, but are
not assigned a value, since all the program can do is compare recognized
characters with each other.
The next step is to assign a value to all recognized characters.
The easiest way to do this is in a Jupyter Notebook, with an interactive
script showing the image of each textline for reference, followed by
an image of each recognized character, with a prompt for its translation.

The information that can be stored for each character is the translation
string, an identifier for the script, and optionally a word distance value.
These values are separated by whitespace, so translation strings cannot
contain spaces.

The script identifier allows for text in different scripts to be parsed
differently, for example syriac from right to left and roman from left to right.
The default script is syriac, denoted by an empty string.
Others are indicated with a letter: `r` for roman, `c` for cursive, `b` for
bold, `s` for small caps.

A Jupyter Notebook is provided in the root directory of the `syrocr` package,
named `UpdateTables.ipynb`.

When all relevant entries have a value assigned to it, the updated tables
can be written to `tables.json` and used to generate the recognized text.

### Ambiguous characters

When it is not immediately clear what the translation of the character should
be, this can be indicated with a question mark. For example, a dalath or
resh can be separated from its dot. This can be indicated with (e.g.) the
translation `D?`.
All instances of characters containing questions marks can then be reviewed,
and corrected with a rule in the corrections file (see below).

Some characters are broken. When this is clear (such as in case of final kaph),
the two parts can be assigned the same value with a plus sign: `K+` and `+K`.
These will be automatically joined by the gettext program.
When one of the parts is not disconnected from the next character, this would
give values such as `K+` and `+yK` (a yudh followed by a broken kaph).
These will not be automatically joined, so a combination rule must be added
to the corrections file.

### Corrections and combinations

Since the character recognition is not (yet) perfect, some systematic
or individual corrections must be applied to the results.
There are two mechanisms for that now, both of which are stored in a
simple [YAML](https://yaml.org/) corrections file.
This file contains two lists, one named `combinations` and one named
`corrections`. An example of a file `corrections.yaml`:

```yaml
combinations:
  # not disconnected yudh followed by broken kaph
  - [['K+', '+yK'], 'yK']
corrections:
  # r dot cut off by getlines
  - [['mitchell2_test-02', 28, 3, 149], 'r']
  # dotless dalath/resh:
  - [['mitchell2_test-02', 4, 6, 149], 'D']
```

The `combinations` are a list of the translations to be combined, followed
by the correct translation.
The `corrections` correct individual characters, indicated by a list
with the basename of the image (the part of the filename before `.tif`),
line number, character number, and id number, followed by the correct
translation.

An advantage of using YAML instead of JSON is that it is easier to write
and that it allows comments to describe the corrections.

Generating the text
-------------------

When all characters are assigned and all corrections are made, the final
text can be generated. This is done with the `gettext` program:

    $ syrocr gettext json_textlines_dir json_tables_file

The optional corrections file can be added with the `-cf` argument.
If the `_textlines.json` files are in the current directory, the
corrections file is called `corrections.yaml` and the tables file
`tables.json`, we can generate the text with the command:

    $ syrocr gettext . tables.json -cf corrections.yaml

This sends the recognized text to stdout, from where it can be redirected
to a file or piped to another program. Example:

    $ syrocr gettext . tables.json -cf corrections.yaml
    lktb' $ryr'
    d`dt' =. klhwn
    ywlpn' hwyn shdyn
    d$ryryn 'nwn
    lktb' dyn d'yt
    S'dyhwn dywlpn'
    hw hw ywlpn'
    blHwd shdyn
    `lyhwn mTl
    dktb' d`dt'
    ktbyhwn dywlpn'
    l' mshdyn
    shdyn twb^. `l
    ktbyn 'pyhw"dy'
    bkl 'tr gyr
    * * ' * * * ww
    dnhwwn * * hwn
    * * * * * * l
    w'zl 'p * '
    bdyd` hw' gyr
    'lh' dywlpn'
    `tydyn 'nwn
    lmpq b`lm' qdm
    `bd 'twt'
    rwrbt' kd
    mt`qb hw'
    * * * wplg
    ym' w`nn' w`mq'
    wywn wmnn' wdl
    b'trn wkl
    p' * * l' sD * *
    `l kl 'trn
    `mh dylh twb
    dkn$wth d`m'
    * * * * * * *
    * * * * * hwt
