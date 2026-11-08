"""Read-only Blender artifact audit. NEVER creates, edits, or saves the scene."""
import bpy
import json
import math
import sys
from pathlib import Path

objects=[]
for obj in bpy.data.objects:
    item={'name':obj.name,'type':obj.type,'modifiers':[]}
    for mod in obj.modifiers:
        value={'name':mod.name,'type':mod.type,'visible':mod.show_viewport}
        if mod.type=='BEVEL':value.update(width=mod.width,segments=mod.segments,affect=mod.affect,
            width_type=mod.offset_type,limit_method=mod.limit_method,angle_limit_degrees=math.degrees(mod.angle_limit))
        if mod.type=='NODES':value['node_group']=mod.node_group.name if mod.node_group else None
        item['modifiers'].append(value)
    if obj.type=='MESH':
        item.update(base_vertices=len(obj.data.vertices),base_faces=len(obj.data.polygons),smooth_faces=sum(p.use_smooth for p in obj.data.polygons))
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        item.update(evaluated_vertices=len(mesh.vertices),evaluated_faces=len(mesh.polygons),evaluated_smooth_faces=sum(p.use_smooth for p in mesh.polygons))
        evaluated.to_mesh_clear()
    objects.append(item)
result={'blender_version':bpy.app.version_string,'file':bpy.data.filepath,'objects':objects}
Path(sys.argv[sys.argv.index('--')+1]).write_text(json.dumps(result,indent=2))
print('APPDNA_READ_ONLY_AUDIT:'+json.dumps(result))
