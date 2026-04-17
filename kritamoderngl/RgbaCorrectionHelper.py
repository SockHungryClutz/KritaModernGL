"""
Class to help correcting the order of color channels for 8 and 16 bit uint RGBA color depth and mode
Krita defaults these color modes to have the channels in BGRA order
OpenGL can easily swizzle inputs to correct for this, but output is more complicated

Computationally fastest solution is to add output = output.bgra; to the last line of the user's main function
...but this would require checking every output layer to see if this is needed, tracking where each output is mapped,
and finding where the last line of the main function is, but this can easily go awry.

The safe but complicated solution is to track the layers that need this, then build a second shader to run after the
user's shader to correct each output where it's necessary. This also means more buffers need to be created, and more
computation time is required, which is not ideal, but it should be relatively small cost as far as the user can see.

This will be enabled through a checkbox that the user can inspect to learn more.
"""

vertexShader = """#version 330 core

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
}"""

class RgbaCorrectionHelper:
    texturesToReplace = []
    correctedTextures = []
    frameBuffer = None
    program = None
    vao = None

    def __init__(self):
        self.texturesToReplace = []
        self.correctedTextures = []
        self.frameBuffer = None
        self.program = None
        self.vao = None

    # Check if this Krita node needs blue and red channels swapped
    def nodeNeedsCorrection(self, node):
        return (node and node.colorDepth()[0] == "U" and node.colorModel() == "RGBA")

    # If node needs correction, apply swizzle to texture, only works on inputs
    def swizzleTextureIfNeeded(self, node, texture):
        if self.nodeNeedsCorrection(node):
            texture.swizzle = "BGRA"

    # If node needs correction, save a reference to the texture to use later
    def fixTextureIfNeeded(self, node, texture):
        # This will simply track the texture until it is time to build the correction shader
        if self.nodeNeedsCorrection(node):
            self.texturesToReplace.append(texture)

    # If any textures are saved, then the correction pass needs to happen
    def correctionPassNeeded(self):
        return len(self.texturesToReplace) > 0

    # Create a shader using the number of saved textures, which will be bound later
    def generateFragmentShader(self):
        fragShader = "#version 330 core\n\n"
        for i in range(len(self.texturesToReplace)):
            fragShader += f"uniform usampler2D in_texture{i};\nlayout(location = {i}) out uvec4 out_color{i};\n"
        fragShader += "void main() {\n    vec2 texSize  = textureSize(in_texture0, 0).xy;\n    vec2 texCoord = gl_FragCoord.xy / texSize;\n"
        for i in range(len(self.texturesToReplace)):
            fragShader += f"\n    uvec4 color{i} = texture(in_texture{i}, texCoord);\n    out_color{i} = color{i};"
        fragShader += "\n}"
        return fragShader

    # Create a shader program for correction
    def generateProgram(self, ctx):
        return ctx.program(vertex_shader = vertexShader, fragment_shader = self.generateFragmentShader())

    # Binds the saved textures to be used as input for correction shader
    def bindTextures(self, program):
        for i in range(len(self.texturesToReplace)):
            self.texturesToReplace[i].use(location = i)
            self.texturesToReplace[i].swizzle = "BGRA"
            program[f"in_texture{i}"] = i

    # Create textures for the framebuffer output to store the correction
    def createFrameBuffer(self, ctx, doc):
        if self.correctedTextures:
            # There is likely textures and a framebuffer from a previous pass that needs to be cleaned up
            for t in self.correctedTextures:
                t.release()
            self.frameBuffer.release()
            self.correctedTextures = []
        colorDepth = doc.colorDepth()[0].lower() + str(int(doc.colorDepth()[1:]) // 8)
        for i in range(len(self.texturesToReplace)):
            self.correctedTextures.append(ctx.texture((doc.width(), doc.height()), 4, dtype=colorDepth))
        return ctx.framebuffer(self.correctedTextures)

    # Create the vertex array to use for rendering... the actual vertices are in the vertex shader
    def createVertexArray(self, ctx, program):
        vao = ctx.vertex_array(program, [])
        vao.vertices = 6
        vao.mode = ctx.TRIANGLES
        return vao

    # Perform the rendering operation to correct color channels
    def renderCorrectionIfNeeded(self, ctx, doc):
        if not self.correctionPassNeeded():
            return
        self.program = self.generateProgram(ctx)
        self.bindTextures(self.program)
        self.frameBuffer = self.createFrameBuffer(ctx, doc)
        self.frameBuffer.use()
        self.vao = self.createVertexArray(ctx, self.program)
        ctx.clear()
        self.vao.render()
        ctx.finish()
        self.texturesToReplace = []

    # This will iterate over the corrected textures to return them one by one
    def getNextCorrectedTexture(self):
        # Rotating the list means we don't need to keep track of how many we've actually returned
        self.correctedTextures = self.correctedTextures[1:] + self.correctedTextures[:1]
        return self.correctedTextures[-1]

    # Clean up all OGL objects created in rendering process, call after using all the outputs
    def cleanUp(self):
        # texturesToCorrect is not included in cleanup because they belong to the parent
        for tex in self.correctedTextures:
            tex.release()
        self.correctedTextures = []
        if self.frameBuffer:
            self.frameBuffer.release()
        if self.program:
            self.program.release()
        if self.vao:
            self.vao.release()
