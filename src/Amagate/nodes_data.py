mat_nodes = {
    "nodes": [
        {
            "type": "ShaderNodeOutputMaterial",
            "name": "Material Output",
            "properties": {
                "location": (1360.8070068359375, -373.6889343261719),
                "select": False,
                "is_active_output": True,
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeTexCoord",
            "name": "Texture Coordinate",
            "properties": {
                "location": (281.8217468261719, -289.3365173339844),
                "select": False,
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeMapping",
            "name": "Mapping",
            "properties": {
                "location": (650.024169921875, -373.0181884765625),
                "select": False,
                "vector_type": "TEXTURE",
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeTexImage",
            "name": "Image Texture",
            "properties": {
                "location": (818.7850952148438, -374.98919677734375),
                "select": False,
                "projection": "BOX",
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeBsdfPrincipled",
            "name": "Principled BSDF",
            "properties": {"location": (1088.6728515625, -331.3340148925781)},
            "inputs": [
                {"idx": 2, "name": "Roughness", "value": 1.0},
                {"idx": 3, "name": "IOR", "value": 1.0},
            ],
        },
        {
            "type": "ShaderNodeAttribute",
            "name": "Attribute.004",
            "properties": {
                "location": (285.5971984863281, -541.84423828125),
                "select": False,
                "attribute_name": "tex_rotate",
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeAttribute",
            "name": "Attribute.005",
            "properties": {
                "location": (448.6221618652344, -540.6082763671875),
                "select": False,
                "attribute_name": "tex_scale",
            },
            "inputs": [],
        },
        {
            "type": "ShaderNodeAttribute",
            "name": "Attribute.006",
            "properties": {
                "location": (120.35049438476562, -541.9117431640625),
                "select": False,
                "attribute_name": "tex_pos",
            },
            "inputs": [],
        },
    ],
    "links": [
        {
            "from_node": "Texture Coordinate",
            "from_socket": "Object",
            "to_node": "Mapping",
            "to_socket": "Vector",
        },
        {
            "from_node": "Image Texture",
            "from_socket": "Color",
            "to_node": "Principled BSDF",
            "to_socket": "Base Color",
        },
        {
            "from_node": "Principled BSDF",
            "from_socket": "BSDF",
            "to_node": "Material Output",
            "to_socket": "Surface",
        },
        {
            "from_node": "Attribute.006",
            "from_socket": "Vector",
            "to_node": "Mapping",
            "to_socket": "Location",
        },
        {
            "from_node": "Attribute.004",
            "from_socket": "Vector",
            "to_node": "Mapping",
            "to_socket": "Rotation",
        },
        {
            "from_node": "Attribute.005",
            "from_socket": "Vector",
            "to_node": "Mapping",
            "to_socket": "Scale",
        },
        {
            "from_node": "Mapping",
            "from_socket": "Vector",
            "to_node": "Image Texture",
            "to_socket": "Vector",
        },
    ],
}
