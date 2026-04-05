"""Blender script: Glass watermelon being sliced in half.

Run with: ~/blender/blender-4.3.2-linux-x64/blender --background --python scripts/blender_glass_watermelon.py

Creates a 5-second animation of a knife cutting through a glass watermelon
with realistic physics, glass material, and light refraction.
Output: output/run_test/satisfying/blender_watermelon.mp4
"""

import bpy
import math
import os

# ========== CLEANUP ==========
bpy.ops.wm.read_factory_settings(use_empty=True)

# ========== SETTINGS ==========
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "run_test", "satisfying")
os.makedirs(OUTPUT_PATH, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_PATH, "frames"), exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
# scene.cycles.device = 'CPU'
# scene.cycles.samples = 64  # Lower for speed, increase for quality
scene.render.resolution_x = 720
scene.render.resolution_y = 1280
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 150  # 5 seconds at 30fps
scene.render.filepath = os.path.join(OUTPUT_PATH, "frames", "frame_")
scene.render.image_settings.file_format = 'PNG'

# ========== WORLD ==========
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.95, 0.95, 0.95, 1)  # Light gray background
bg.inputs[1].default_value = 1.0

# ========== MATERIALS ==========

# Glass watermelon exterior (green glass)
mat_exterior = bpy.data.materials.new("GlassExterior")
mat_exterior.use_nodes = True
nodes = mat_exterior.node_tree.nodes
nodes.clear()
output = nodes.new("ShaderNodeOutputMaterial")
glass = nodes.new("ShaderNodeBsdfGlass")
glass.inputs["Color"].default_value = (0.1, 0.6, 0.15, 1)  # Green
glass.inputs["Roughness"].default_value = 0.05
glass.inputs["IOR"].default_value = 1.5
mat_exterior.node_tree.links.new(glass.outputs[0], output.inputs[0])

# Glass watermelon interior (red glass)
mat_interior = bpy.data.materials.new("GlassInterior")
mat_interior.use_nodes = True
nodes = mat_interior.node_tree.nodes
nodes.clear()
output = nodes.new("ShaderNodeOutputMaterial")
glass = nodes.new("ShaderNodeBsdfGlass")
glass.inputs["Color"].default_value = (0.8, 0.1, 0.15, 1)  # Red
glass.inputs["Roughness"].default_value = 0.02
glass.inputs["IOR"].default_value = 1.45
mat_interior.node_tree.links.new(glass.outputs[0], output.inputs[0])

# Knife material (metallic)
mat_knife = bpy.data.materials.new("Knife")
mat_knife.use_nodes = True
nodes = mat_knife.node_tree.nodes
nodes.clear()
output = nodes.new("ShaderNodeOutputMaterial")
glossy = nodes.new("ShaderNodeBsdfGlossy")
glossy.inputs["Color"].default_value = (0.8, 0.8, 0.85, 1)
glossy.inputs["Roughness"].default_value = 0.1
mat_knife.node_tree.links.new(glossy.outputs[0], output.inputs[0])

# Marble board
mat_marble = bpy.data.materials.new("Marble")
mat_marble.use_nodes = True
nodes = mat_marble.node_tree.nodes
nodes.clear()
output = nodes.new("ShaderNodeOutputMaterial")
principled = nodes.new("ShaderNodeBsdfPrincipled")
principled.inputs["Base Color"].default_value = (0.9, 0.88, 0.85, 1)
principled.inputs["Roughness"].default_value = 0.3
mat_marble.node_tree.links.new(principled.outputs[0], output.inputs[0])

# ========== OBJECTS ==========

# Cutting board
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, -0.15))
board = bpy.context.active_object
board.name = "CuttingBoard"
board.scale = (2, 1.5, 0.1)
board.data.materials.append(mat_marble)

# Watermelon exterior (elongated sphere) - LEFT HALF
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(-0.28, 0, 0.35))
wm_left = bpy.context.active_object
wm_left.name = "WatermelonLeft"
wm_left.scale = (0.5, 0.8, 0.7)
wm_left.data.materials.append(mat_exterior)

# Watermelon exterior - RIGHT HALF
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0.28, 0, 0.35))
wm_right = bpy.context.active_object
wm_right.name = "WatermelonRight"
wm_right.scale = (0.5, 0.8, 0.7)
wm_right.data.materials.append(mat_exterior)

# Interior cross-section (flat disc visible between halves)
bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=0.02, location=(0, 0, 0.35))
interior = bpy.context.active_object
interior.name = "Interior"
interior.scale = (1, 0.7, 1)
interior.rotation_euler = (0, math.radians(90), 0)
interior.data.materials.append(mat_interior)

# Knife blade
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.2))
knife = bpy.context.active_object
knife.name = "Knife"
knife.scale = (0.01, 0.6, 0.4)
knife.data.materials.append(mat_knife)

# Knife handle (extends up out of frame)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 1.8))
handle = bpy.context.active_object
handle.name = "KnifeHandle"
handle.scale = (0.04, 0.15, 0.3)
handle.data.materials.append(mat_knife)

# Parent handle to knife
handle.parent = knife

# ========== ANIMATION ==========

# Knife starts above, cuts down through watermelon
# Frame 1: Knife above
knife.location = (0, 0, 1.2)
knife.keyframe_insert(data_path="location", frame=1)

# Frame 45 (1.5s): Knife touches top of watermelon
knife.location = (0, 0, 0.75)
knife.keyframe_insert(data_path="location", frame=45)

# Frame 90 (3s): Knife has cut through to board
knife.location = (0, 0, -0.05)
knife.keyframe_insert(data_path="location", frame=90)

# Frame 150 (5s): Knife rests on board
knife.location = (0, 0, -0.05)
knife.keyframe_insert(data_path="location", frame=150)

# Watermelon halves: start together, split apart after cut
# Left half
wm_left.location = (0, 0, 0.35)
wm_left.keyframe_insert(data_path="location", frame=1)
wm_left.location = (0, 0, 0.35)
wm_left.keyframe_insert(data_path="location", frame=80)
wm_left.location = (-0.4, 0, 0.3)
wm_left.rotation_euler = (0, 0, math.radians(-8))
wm_left.keyframe_insert(data_path="location", frame=120)
wm_left.keyframe_insert(data_path="rotation_euler", frame=120)

# Right half
wm_right.location = (0, 0, 0.35)
wm_right.keyframe_insert(data_path="location", frame=1)
wm_right.location = (0, 0, 0.35)
wm_right.keyframe_insert(data_path="location", frame=80)
wm_right.location = (0.4, 0, 0.3)
wm_right.rotation_euler = (0, 0, math.radians(8))
wm_right.keyframe_insert(data_path="location", frame=120)
wm_right.keyframe_insert(data_path="rotation_euler", frame=120)

# Interior disc: invisible at first, appears as halves split
interior.scale = (0, 0.7, 1)
interior.keyframe_insert(data_path="scale", frame=1)
interior.scale = (0, 0.7, 1)
interior.keyframe_insert(data_path="scale", frame=80)
interior.scale = (1, 0.7, 1)
interior.keyframe_insert(data_path="scale", frame=100)

# ========== CAMERA ==========
bpy.ops.object.camera_add(location=(2.5, -2, 1.2))
camera = bpy.context.active_object
camera.name = "Camera"
scene.camera = camera

# Point camera at the watermelon
constraint = camera.constraints.new('TRACK_TO')
constraint.target = wm_left
constraint.track_axis = 'TRACK_NEGATIVE_Z'
constraint.up_axis = 'UP_Y'

# Camera settings for nice DOF
camera.data.lens = 85
camera.data.dof.use_dof = True
camera.data.dof.focus_object = wm_left
camera.data.dof.aperture_fstop = 2.8

# ========== LIGHTING ==========
# Key light
bpy.ops.object.light_add(type='AREA', location=(2, -1, 3))
key_light = bpy.context.active_object
key_light.data.energy = 200
key_light.data.size = 2

# Fill light
bpy.ops.object.light_add(type='AREA', location=(-2, -1, 2))
fill_light = bpy.context.active_object
fill_light.data.energy = 80
fill_light.data.size = 3

# Back light for glass refraction
bpy.ops.object.light_add(type='AREA', location=(0, 2, 2))
back_light = bpy.context.active_object
back_light.data.energy = 150
back_light.data.size = 2

# ========== RENDER ==========
print(f"Rendering to: {scene.render.filepath}")
bpy.ops.render.render(animation=True)
print("Render complete!")
