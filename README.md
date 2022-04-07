# Grease Pencil Color Picker

Blender add-on to quickly switch between a given set of grease pencil materials.

## Usage

### Create palette
In the viewport, press Ctrl+Shift+A to launch the palette editor mode.
Add a palette by clicking on the cross in the gray circle, and entering a name.
You can then : 
* Add, move or remove a material in the palette,
* add or edit a palette image,
* add, move or remove picklines for each material,
* assign brushes for materials.

### Picker FROM PALETTE
* Go to Properties > Scene > Grease Pencil palettes, and click on the *Load File* icon.
* Select the JSON file you want to import, the palettes should appear in the list on the panel
* You can use the buttons in the list to reload or remove a certain palette. You can also click on a palette to make it *active*
* Select a Grease Pencil object, switch to draw mode.
* Press A. The active palette should appear as an icon. 
* You can switch between palettes using Tab (or Shift+Tab to switch in reversed order).
* Select a material : you've added that material to the active GP object and made it the active material.

![Load File](doc/load_file_instructions.png "Loading a JSON file from the Blender interface")

### Picker FROM ACTIVE 
* Select a Grease Pencil object,
* Switch to Draw Mode,
* Press A. The list of materials now appear in a wheel-like menu.
* Press Tab to switch current palette (if multiple palettes).
* Left-click on one of the materials to make it active,
* Or right-click (or press ESC) to cancel the operation

![Preview](doc/gcp_preview.png "Preview of the GP Color Picker")


## JSON File Specification
At the root of the JSON file, we should find a list of palettes specified by their name, and containing : 

- "materials" \[MANDATORY\] : containing a list of materials and their specification (*). 

- "image" \[OPTIONAL\] : image to be displayed in the center of the tool

    - "path" \[MANDATORY\] : path of the image file

    - "relative" \[OPTIONAL\] : whether the path is relative or absolute (default=True)

(*) Each material contains : 

- "name" of the material (if a material of the same name already exists, it will be updated with the specified parameters)

    - unordered list of material specification fields, all possible fields and default values are written [here](doc/base_material.json)

    - "position" \[OPTIONAL\] : angle position of the material in the wheel

    - "image" \[OPTIONAL\] : an image to be displayed in the tool when the material is hoverred by the cursor

    - "layer" \[OPTIONAL\] : the name of the layer to switch to when the material is selected (only applies if the root field "image" contains a valid path)


An example of valid JSON file can be found [here](doc/example.json)

## License

Published under GPLv3 license.
