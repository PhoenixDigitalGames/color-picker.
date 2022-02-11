import bpy
import numpy as np
from math import atan2,pi,floor
from . drw import draw_callback_px, load_gpu_texture
from . stg import GPCOLORPICKER_settings
import gpu

settings = GPCOLORPICKER_settings()

### ----------------- Operator definition
class GPCOLORPICKER_OT_wheel(bpy.types.Operator):
    bl_idname = "gpencil.color_pick"
    bl_label = "GP Color Picker"    
    
    def __init__(self): pass            
    def __del__(self): pass

    @classmethod
    def poll(cls, context):
        return  (context.area.type == 'VIEW_3D') and \
                (context.mode == 'PAINT_GPENCIL') and \
                (context.active_object is not None) and \
                (context.active_object.type == 'GPENCIL')

    def get_selected_mat_id(self,event):
        # Find mouse position
        mouse_pos = np.asarray([event.mouse_region_x,event.mouse_region_y]) - 0.5*settings.region_dim
        
        # Check in which section of the circle the mouse is located
        mouse_local = mouse_pos - settings.origin
        if np.linalg.norm(mouse_local) < settings.interaction_radius:
            return -1     

        dt = atan2(mouse_local[1], mouse_local[0]) % (2*pi)
        if not settings.useCustomAngles():
            return int(floor((dt*settings.mat_nb/pi + 1)/2)) % (settings.mat_nb)
          
        th = settings.custom_angles
        n = settings.mat_nb

        if n < 2:
            return 0

        # specific case of i = 0
        alpha = 0.5*(th[0] + th[n-1])
        if not ( (dt >= 0.5*(th[0] + th[1])) \
            and ( ( alpha > pi ) or ( dt < alpha + pi ) ) \
            and ( ( alpha < pi ) or ( dt < alpha - pi ) )  ):
            return 0

        # general case : i > 0 and i < mat_nb - 1
        i = 1
        while( i < n - 1 ):
            beta = 2*dt-th[i]
            if( (beta >= th[i-1]) and (beta <= th[i+1])):
                return i
            i += 1
        # case i = mat_nb-1 is handled by default
        return n-1


    def modal(self, context, event):
        context.area.tag_redraw()

        def validate_selection():
            i = settings.mat_selected
            if (i < 0) or (i >= settings.mat_nb):
                return False

            if not settings.mat_from_active:
                ob_mat = settings.active_obj.data.materials                
                mat = settings.materials[i]
                i = ob_mat.find(mat.name)
                if i < 0:
                    i = len(ob_mat)
                    ob_mat.append(mat)

            settings.active_obj.active_material_index = i
            
            return True

        if event.type == 'MOUSEMOVE':
            settings.mat_selected = self.get_selected_mat_id(event)
        
        elif ((event.type == settings.key_shortcut) \
                and (event.value == 'RELEASE')):
            if validate_selection():       
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                return {'FINISHED'}
                
        elif (event.type == 'LEFTMOUSE'):
            validate_selection()          
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def load_active_materials(self):
        s = settings

        if s.active_obj is None:
            # Should be avoided by poll function but who knows
            self.report({'ERROR'}, "No active object")
            return False

        s.materials = [ m.material for k,m in s.active_obj.material_slots.items() \
                                    if m.material.is_grease_pencil ]       
        s.mat_nb = min(s.mat_nmax,len(s.materials))
        s.mat_active = s.active_obj.active_material_index

        if s.mat_nb == 0:
            self.report({'INFO'}, "No material in the active object")
            return False
        return True
    
    def load_from_palette(self):
        s = settings
        palette = bpy.context.scene.gpmatpalette
        s.materials = [ bpy.data.materials[n.mat_name] for n in palette.materials ]       
        s.mat_nb = min(s.mat_nmax,len(s.materials))
        s.mat_active = -1

        if s.mat_nb == 0:
            self.report({'INFO'}, "No JSON file or empty file")
            return False
        
        if palette.hasCustomAngles():
            s.custom_angles = [ m.custom_angle for m in palette.materials ]
        else:
            s.custom_angles = []

        return True
    
    def load_grease_pencil_materials(self):
        s = settings

        if s.mat_from_active:
            flag = self.load_active_materials()
        else:
            flag = self.load_from_palette()

        if not flag:
            return False

        s.load_mat_radius()
        mat_gp = [ m.grease_pencil for m in s.materials ]
        s.mat_fill_colors = [ m.fill_color if m.show_fill else ([0.,0.,0.,0.]) for m in mat_gp ]
        s.mat_line_colors = [ m.color if m.show_stroke else ([0.,0.,0.,0.]) for m in mat_gp ] 
        
        return True

    def load_preferences(self, prefs):
        settings.mat_from_active = (prefs.mat_mode == "from_active")

        if not settings.mat_from_active:
            gpmp = bpy.context.scene.gpmatpalette 
            settings.cached_gpu_tex = load_gpu_texture(gpmp.image)

        settings.mc_fill_color = prefs.theme.pie_color
        settings.mc_line_color = prefs.theme.line_color
        settings.text_color = prefs.theme.text_color
        settings.set_icon_scale(prefs.icon_scale)

    def invoke(self, context, event):  
        # Update settings from user preferences
        prefs = context.preferences.addons[__package__].preferences
        if prefs is None : 
            self.report({'WARNING'}, "Could not load user preferences, running with default values")
        else:
            self.load_preferences(prefs)

        settings.active_obj = bpy.context.active_object

        # Loading materials 
        if not (self.load_grease_pencil_materials()):
            return {'CANCELLED'}  

        # Setting modal handler
        self._handle = context.window_manager.modal_handler_add(self)
        if not self._handle:
            return {'CANCELLED'}  

        # Get mouse position
        region = bpy.context.region
        settings.region_dim = np.asarray([region.width,region.height])
        settings.origin = np.asarray([event.mouse_region_x,event.mouse_region_y]) - 0.5*settings.region_dim  
        self._handle = context.space_data.draw_handler_add(draw_callback_px, (self,context,settings), \
                                                        'WINDOW', 'POST_PIXEL')
        return {'RUNNING_MODAL'}    