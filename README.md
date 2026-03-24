# KritaModernGL - GLSL Programming in Krita

Plugin for programming vertex, fragment, and compute shaders in Krita.  

* Supports all color depths and formats as input and output  
* Use the currently selected layer as a texture input, or any layer in the document  
* The result can be added to a new layer above the current layer, or overwrite an existing layer  
* Multiple input and output textures can be used  

## How to Install

 1. Open Krita, go to Settings->Manage Resources...->Open Resource Folder
 2. Open the pykrita folder inside the folder that pops up
 3. Download the zip file from the [Releases page](https://github.com/SockHungryClutz/KritaModernGL/releases)
 4. Extract the zip file into the pykrita folder from step 2
 5. Close and reopen Krita
 6. Go to Settings->Configure Krita->Python Plugin Manager
 7. Scroll down and enable KritaModernGL, click OK to save
 8. Close and reopen Krita again

## How to Use

Find the OpenGL tool to use under the Tools menu. You can choose which layer to map to each texture unit in the menu. Any errors in your program will appear in the UI.  

Use the **Help** button to see a more descriptive explanation of each option.

## Examples

Vertex shader that covers the whole image, the number of vertices to render should be set to 6 to render all vertices in the array
```
#version 330 core

vec3 vertices[6] = vec3[](
    vec3(-1.0, 1.0, 0.0),
    vec3(-1.0, -1.0, 0.0),
    vec3(1.0, -1.0, 0.0),
    vec3(1.0, -1.0, 0.0),
    vec3(1.0, 1.0, 0.0),
    vec3(-1.0, 1.0, 0.0)
);

void main() {
    gl_Position = vec4(vertices[gl_VertexID], 1.0);
}
```

Fragment shader that slightly shifts the red and blue channels
```
#version 330 core

uniform usampler2D in_texture;
layout(location = 0) out uvec4 out_color;

void main() {
    vec2 texSize  = textureSize(in_texture, 0).xy;
    vec2 texCoord = gl_FragCoord.xy / texSize;

    uvec4 rValue = uvec4(texture(in_texture, texCoord + 0.005));
    uvec4 gValue = uvec4(texture(in_texture, texCoord));
    uvec4 bValue = uvec4(texture(in_texture, texCoord - 0.005));
    out_color = uvec4(rValue.r, gValue.g, bValue.b, 255);
}
```

Compute shader that swaps the color channels, set the Workgroup X variable to 1/16 the X axis size and Workgroup Y to 1/16 the Y axis size, eg. 64 for both would cover a 1024x1024 area
```
#version 450

layout (local_size_x = 16, local_size_y = 16) in;

layout (binding = 0, rgba8ui) uniform uimage2D out_texture;
layout (binding = 1, rgba8ui) uniform uimage2D in_texture;

void main() {
    ivec2 tex_pos = ivec2(gl_GlobalInvocationID.xy);
    uvec4 color = imageLoad(in_texture, tex_pos);
    uvec4 flipped_color = color.gbra;
    imageStore(out_texture, tex_pos, flipped_color);
}
```

### Extra Notes

This plugin relies on the ModernGL and GLContext python modules, provided under the MIT license. A copy of this licence is provided in this repository. This plugin is provided under the same license.
