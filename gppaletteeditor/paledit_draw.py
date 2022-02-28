import blf, bpy
import gpu
from gpu_extras.batch import batch_for_shader
import numpy as np
from math import *
import os
from .. gpcolorpicker import picker_draw as gpcp

edition_layer_fsh = '''
#define PI 3.1415926538
uniform vec2 mark_origin;
uniform vec4 mark_color;
uniform float mark_radius;
uniform float aa_eps;

in vec2 lpos;
in vec2 uv;
out vec4 fragColor;   

float aa_circle(float rds, float dst, float eps){
    return smoothstep(rds+eps, rds-eps, dst);
}       

vec4 alpha_compose(vec4 A, vec4 B){
    /* A over B */
    vec4 color = vec4(0.);
    color.a = A.a + B.a*(1.- A.a);
    if( color.a == 0. ){
        return color;
    }
    color.rgb = (A.rgb * A.a + B.rgb * B.a * (1 - A.a))/(color.a);
    return color;
} 

void main()
{                    
    float d = length(lpos-mark_origin);  

    vec4 fragColor_origin= mark_color;
    fragColor_origin.a *= aa_circle(mark_radius, d, aa_eps); 
    fragColor = fragColor_origin;  
}
'''

def draw_edition_layer(op, context, cache, settings):
    shader, batch = gpcp.setup_shader(op, settings, edition_layer_fsh)

    mark = op.interaction_in_selection.mark
    shader.uniform_float("mark_origin", mark.position) 
    shader.uniform_float("mark_radius", mark.radius) 
    shader.uniform_float("mark_color", mark.color) 
    shader.uniform_float("aa_eps", settings.anti_aliasing_eps) 

    batch.draw(shader)  


def draw_callback_px(op, context, cache, settings): 
    gpcp.draw_callback_px(op, context, cache, settings)  

    gpu.state.blend_set('ALPHA') 
    
    if op.interaction_in_selection and op.interaction_in_selection.has_mark():
        draw_edition_layer(op, context, cache, settings)

    # Reset blend mode
    gpu.state.blend_set('NONE')
    # op.check_time()
    