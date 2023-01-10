import os
import rasterio
#from rasterio.io import MemoryFile
import warnings
import numpy as np
from imagepacker.utils import AABB
from imagepacker import pack

warnings.filterwarnings("ignore", category=rasterio.errors.NotGeoreferencedWarning)

def load_obj(obj_path, _info=print):
    if not os.path.isfile(obj_path):
        raise IOError("Cannot open %s" % obj_path)

    obj_base_path = os.path.dirname(os.path.abspath(obj_path))
    obj = {
        'materials': {},
    }
    vertices = []
    uvs = []
    normals = []

    faces = {}
    current_material = "_"

    with open(obj_path) as f:
        _info("Loading %s" % obj_path)

        for line in f:
            if line.startswith("mtllib "):
                # Materials
                mtl_file = "".join(line.split()[1:]).strip()
                obj['materials'].update(load_mtl(mtl_file, obj_base_path, _info=_info))
            elif line.startswith("v "):
                # Vertices
                vertices.append(list(map(float, line.split()[1:4])))
            elif line.startswith("vt "):
                # UVs
                uvs.append(list(map(float, line.split()[1:3])))
            elif line.startswith("vn "):
                normals.append(list(map(float, line.split()[1:4])))
            elif line.startswith("usemtl "):
                mtl_name = "".join(line.split()[1:]).strip()
                if not mtl_name in obj['materials']:
                    raise Exception("%s material is missing" % mtl_name)

                current_material = mtl_name
            elif line.startswith("f "):
                if current_material not in faces:
                    faces[current_material] = []

                a,b,c = line.split()[1:]

                if a.count("/") == 2:
                    av, at, an = map(int, a.split("/")[0:3])
                    bv, bt, bn = map(int, b.split("/")[0:3])
                    cv, ct, cn = map(int, c.split("/")[0:3])

                    faces[current_material].append((av - 1, bv - 1, cv - 1, at - 1, bt - 1, ct - 1, an - 1, bn - 1, cn - 1)) 
                else:
                    av, at = map(int, a.split("/")[0:2])
                    bv, bt = map(int, b.split("/")[0:2])
                    cv, ct = map(int, c.split("/")[0:2])
                    faces[current_material].append((av - 1, bv - 1, cv - 1, at - 1, bt - 1, ct - 1)) 

    obj['vertices'] = np.array(vertices, dtype=np.float32)
    obj['uvs'] = np.array(uvs, dtype=np.float32)
    obj['normals'] = np.array(normals, dtype=np.float32)
    obj['faces'] = faces

    return obj

def load_mtl(mtl_file, obj_base_path, _info=print):
    mtl_file = os.path.join(obj_base_path, mtl_file)

    if not os.path.isfile(mtl_file):
        raise IOError("Cannot open %s" % mtl_file)

    mats = {}
    current_mtl = ""

    with open(mtl_file) as f:
        for line in f:
            if line.startswith("newmtl "):
                current_mtl = "".join(line.split()[1:]).strip()
            elif line.startswith("map_Kd ") and current_mtl:
                map_kd_filename = "".join(line.split()[1:]).strip()
                map_kd = os.path.join(obj_base_path, map_kd_filename)
                if not os.path.isfile(map_kd):
                    raise IOError("Cannot open %s" % map_kd)

                mats[current_mtl] = map_kd

                # TODO: remove
                #_info("Loading %s" % map_kd_filename)
                # with MemoryFile() as memfile:
                #     with rasterio.open(map_kd, 'r') as src:
                #         data = src.read()
                #         with memfile.open(driver='JPEG', jpeg_quality=90, count=3, width=src.width, height=src.height, dtype=rasterio.dtypes.uint8) as dst:
                #             for b in range(1, min(3, src.count) + 1):
                #                 # TODO: convert if uint16 or float
                #                 dst.write(data[b - 1], b)
                #     memfile.seek(0)
                #     mats[current_mtl] = memfile.read()
    return mats


def obj_pack(obj_file, output_dir=None):
    if not output_dir:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(obj_file)), "packed")
    
    obj = load_obj(obj_file)

    # Compute AABB for UVs
    extents = {}
    for material in obj['materials']:
        bounds = AABB()

        faces = obj['faces'][material]
        for f in faces:
            for uv_idx in f[3:6]:
                uv = obj['uvs'][uv_idx]
                bounds.add(uv[0], uv[1])

        extents[material] = bounds
    
    output_image, uv_changes, profile = pack(obj, extents=extents)
    # _, h, w = output_image.shape
    # profile['width'] = w
    # profile['height'] = h
    # with rasterio.open(obj_file + "_testout.png", 'w', **profile) as dst:
    #     for b in range(1, output_image.shape[0] + 1):
    #         dst.write(output_image[b - 1], b)
    # exit(1)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Packs textured .OBJ Wavefront files into a single materials")
    parser.add_argument("obj", help="Path to the .OBJ file")
    parser.add_argument("-o","--output-dir", help="Output directory")
    args = parser.parse_args()

    obj_pack(args.obj, args.output_dir)