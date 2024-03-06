# Known (and Tolerated) Bugs and Limitations

Things mentioned here I'm not thrilled about,
but fixing them properly is too much work for a hobby project.

## In the VM

### Console Line Length
Arbitrary-length input is rather a puzzle in C.
The `console!read_line` operation will read at most 2^10-1 bytes from the keyboard (or standard input).
If you supply a longer line, then it is silently split at that boundary.
Whatever comes next is considered part of the next line.

## In the Bug List

The list is not complete.

