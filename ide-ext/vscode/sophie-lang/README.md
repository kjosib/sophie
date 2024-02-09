# Sophie Language Syntax Highlighting for VS-Code

## Features

Basic syntax highlighting for Sophie (`.sg`) files.
Covers keywords, numbers, strings, comments, and a handful of interesting predefined identifiers.

## Requirements

### To Use Directly:

* [vscode](https://code.visualstudio.com/)
* The theme of your choice.

From VS-Code's `control-shift-P` menu,
you can select *>Developer: Install Extension from Location...*
in order to use this extension directly as-is.

### To Build as a Package

If you want to package the extension to pass around,
you'll also need [node.js](https://nodejs.org/).
You can make the extension using something like:

	npm install -g @vscode/vsce
	cd \GitHub\sophie\ide-ext\vscode\sophie-lang
	vsce package

This will create a file called something like `sophie-lang-0.0.1.vsix` which
you can then *>Extensions: Install from VSIX*

## Known Issues

There's not a language server just yet.

## Release Notes

*It says here that "Users appreciate release notes as you update your extension."*


### 0.0.1

Initial release

**Enjoy!**
