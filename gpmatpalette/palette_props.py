import math
import bpy,gpu,os
from bpy.types import PropertyGroup
from bpy.props import *

class GPMatImage(PropertyGroup):
    name: StringProperty(subtype='FILE_NAME')
    path: StringProperty(subtype='FILE_PATH')

    def get(self):
        if not self.is_registered():
            if not self.file_exists():
                return None
            self.reload()
        return bpy.data.images[self.name]

    def is_registered(self):
        return (self.name in bpy.data.images)
    
    def file_exists(self):
        return os.path.isfile(self.path)
    
    def load(self, path, path_prefix="", overload_existing=False):
        self.path = os.path.join(path_prefix, path)
        self.reload(overload_existing)

    def reload(self, check_existing=False):
        im = bpy.data.images.load(filepath=self.path, check_existing=check_existing)
        self.name = im.name
    
    def remove(self):
        if not self.is_registered(): 
            return
        bpy.data.images.remove(bpy.data.images[self.name])
    
    def isempty(self):
        return (self.name == "")

    def clear(self):
        self.remove()
        self.name = ""
        self.path = ""

class GPMatItem(PropertyGroup):
    name: StringProperty()
    custom_angle: FloatProperty(subtype='ANGLE', default=-1)
    image: PointerProperty(type=GPMatImage)
    layer: StringProperty()

    def clear(self):
        # Remove image from database
        self.image.clear()

class GPMatPalette(PropertyGroup):
    bl_idname= "scene.gpmatpalettes.palette"
    name: StringProperty(default="unnamed")
    materials: CollectionProperty(type=GPMatItem)
    image: PointerProperty(type=GPMatImage)
    source_path: StringProperty(subtype='FILE_PATH')
    visible: BoolProperty(default=True)

    # Safety check to use custom angles
    # all materials should have one, and the angles should be in increasing order
    def hasCustomAngles(self):
        a = 0
        for m in self.materials:
            if (m.custom_angle < a) or (m.custom_angle > 2*math.pi):
                return False
            a = m.custom_angle
        return True        
        
    def clear(self):
        for m in self.materials:
            m.clear()
        self.materials.clear()
        self.image.clear()

    def count(self):
        return len(self.materials)

def update_palette_active_index(self,context):
    if self.active_index == -1:
        return
    if self.palettes[self.active_index].visible:
        return
    if not any([p.visible for p in self.palettes]):
        self.active_index = -1
        return
    self.next()
class GPMatPalettes(PropertyGroup):
    bl_idname= "scene.gpmatpalettes"
        
    palettes: CollectionProperty(type=GPMatPalette)
    active_index: IntProperty(default=-1, update=update_palette_active_index)

    def __init__(self):
        self.palettes.clear()
        self.active_index = -1

    def active(self):
        if (self.active_index < 0) or (self.active_index >= len(self.palettes)):
            return None
        return self.palettes[self.active_index]

    def next(self):
        self.active_index = (self.active_index + 1) % len(self.palettes)

    def nextVisible(self):
        if not any([p.visible for p in self.palettes]):
            return

        self.next()
        while not self.palettes[self.active_index].visible:
            self.next()

    def count(self):
        return len(self.palettes)

    def clear(self):
        for p in self.palettes:
            p.clear()

        self.palettes.clear()
        self.active_index = -1

classes = [GPMatImage, GPMatItem, GPMatPalette, GPMatPalettes]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.gpmatpalettes = PointerProperty(type=GPMatPalettes)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    