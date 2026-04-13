# Dumb duplex scan

Many scanners can scan your pages double sided. But some bad ones cannot. This utility is pretty simple. Instead of putting each page in one by one and wasting your life with it, just feed the fronts in the automatic document feeder. Then flip the entire stack upside down and feed that in too. Then this will piece them together into a single PDF in order.

Thus, if I am trying to create a PDF with the fronts and backs of my `annoying stack of documents`, I can have the scanner run through and yield PDFs:
* `annoying stack fronts.pdf` and
* `annoying stack backs reversed.pdf`

The backs are reversed because all I did was flip the entire stack of documents over. This means the last becomes the first. You must name your files with these suffixes.

With this utility I can then:

```
uv run duplex_scans.py "annoying stacks fronts.pdf" "annoying stacks backs.pdf"
# this will create a new file in the same location as the first file
# called "annoying stacks interleaved.pdf"
```

Or, if I have many such documents, I can batch them, if they are in this format:

```
some_temporary_directory/
  annoying stack fronts.pdf
  annoying stack backs reversed.pdf
  bank documents fronts.pdf
  bank documents backs reversed.pdf
  cable docs fronts.pdf
  cable docs backs reversed.pdf
  some bills fronts.pdf
  some bills backs reversed.pdf
```

Executing `uv run duplex_scans.py some_temporary_directory` will construct corresponding `* interleaved.pdf` for each stem (eg `annoying stack` or `some bills`).
