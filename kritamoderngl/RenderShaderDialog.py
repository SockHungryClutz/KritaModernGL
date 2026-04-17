from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths, QEvent, QUuid
from PyQt5.QtGui import QIntValidator, QFont, QIcon
from PyQt5.QtWidgets import QDialog, QFileDialog, QDialogButtonBox, QComboBox, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit, QPushButton, QCheckBox
from . import RenderBufferMapperDialog, RgbaCorrectionHelper

# Dialog box for render shader
class RenderShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(RenderShaderDialog, self).__init__(parent)
        self.ext = extension
        
        self.helpWindow = QMessageBox()
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open |
            QDialogButtonBox.Save |
            QDialogButtonBox.Ok |
            QDialogButtonBox.Help |
            QDialogButtonBox.Cancel,
            self)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("Run")
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(self.applyChanges)
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.openFile)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveFile)
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        self.setWindowModality(Qt.WindowModal)
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)

        # New buffer mapper screen to configure input and output textures
        self.mapWindow = RenderBufferMapperDialog.RenderBufferMapperDialog(self)
        
        self.settingLayout = QHBoxLayout()
        self.vertLabel = QLabel("Vertex Shader:", self)
        self.settingLabel = QLabel("Number of vertices to render:", self)
        self.vertNumber = QLineEdit("-1", self)
        self.vertNumber.setValidator(QIntValidator(-1, 2147483647, self))
        self.settingLabel2 = QLabel("Primitive mode:", self)
        self.vertMode = QComboBox()
        self.vertMode.addItems(
            ["Points",
            "Lines",
            "Line Loop",
            "Line Strip",
            "Triangles",
            "Triangle Strip",
            "Triangle Fan"])
        self.vertMode.setInsertPolicy(QComboBox.NoInsert)
        self.settingSpacer = QLabel("   |   ", self)
        
        self.mapButton = QPushButton("Map Buffers", self)
        self.mapButton.clicked.connect(self.showMap)
        try:
            self.mapWindow.validateMapping()
        except Exception as e:
            self.mapButton.setIcon(Krita.instance().icon("warning"))
            self.mapButton.setToolTip(f"Errors in configuration mapping, open to resolve\nMost likely, previous configuration referred to a layer that does not exist now\n\n{e.args[0]}")
        
        self.settingLayout.addWidget(self.settingLabel)
        self.settingLayout.addWidget(self.vertNumber)
        self.settingLayout.addWidget(self.settingLabel2)
        self.settingLayout.addWidget(self.vertMode)
        self.settingLayout.addWidget(self.settingSpacer)
        self.settingLayout.addWidget(self.mapButton)
        self.vertBox = QTextEdit()
        self.vertBox.setAcceptRichText(False)
        self.vertBox.setTabChangesFocus(False)
        self.vertBox.setFont(monoFont)

        self.rgbaColorCorrector = RgbaCorrectionHelper.RgbaCorrectionHelper()
        self.rgbaCorrectCheck = QCheckBox("Fix RGBA color channel order", self)
        self.rgbaCorrectCheck.setChecked(True)
        self.rgbaCorrectCheck.setToolTip("""Attempt to ensure the red and blue color channels are in the correct order when using RGBA color mode.
When this is checked, RGBA channels should be in the correct order. Else, red and blue channels may be swapped.
If you notice issues with the order of red and blue color channels, try toggling this option.""")
        
        self.fragLabel = QLabel("Fragment Shader:", self)
        self.fragBox = QTextEdit()
        self.fragBox.setAcceptRichText(False)
        self.fragBox.setTabChangesFocus(False)
        self.fragBox.setFont(monoFont)
        
        self.errLabel = QLabel("Errors:", self)
        self.errBox = QTextEdit()
        self.errBox.setAcceptRichText(False)
        self.errBox.setReadOnly(True)
        self.errBox.setPlaceholderText("Enter shader code above and click Run, warnings and errors will appear here.")
        
        vbox = QVBoxLayout(self)
        vbox.addLayout(self.settingLayout)
        vbox.addWidget(self.rgbaCorrectCheck)
        vbox.addWidget(self.vertLabel)
        vbox.addWidget(self.vertBox)
        vbox.addWidget(self.fragLabel)
        vbox.addWidget(self.fragBox)
        vbox.addWidget(self.errLabel)
        vbox.addWidget(self.errBox)
        vbox.addWidget(self.buttonBox)
        
        self.readSettings()
        
        self.setWindowTitle("OpenGL Shader Programming")
        self.setSizeGripEnabled(True)
        self.installEventFilter(self)
        self.show()
        self.activateWindow()
        
        # For some reason, the geometry as applied differs from how it should be
        # Save the difference and apply it on save
        self.geometryDelta = QRect(
            self.geometry().x() - self.readGeometry.x(),
            self.geometry().y() - self.readGeometry.y(),
            self.geometry().width() - self.readGeometry.width(),
            self.geometry().height() - self.readGeometry.height())

    def eventFilter(self, obj, event):
        # Because QDialog is a widget and not a window (even though it's literally a window),
        # this filter is needed to detect when the window (widget) receives focus
        # because the widget does not receive focus events when the window receives focus
        if event.type() == QEvent.WindowActivate:
            try:
                self.mapWindow.validateMapping()
                self.mapButton.setIcon(QIcon())
                self.mapButton.setToolTip("")
            except Exception as e:
                self.mapButton.setIcon(Krita.instance().icon("warning"))
                self.mapButton.setToolTip(f"Errors in configuration mapping, open to resolve\nMost likely, previous configuration referred to a layer that does not exist now\n\n{e.args[0]}")
            return True
        return super().eventFilter(obj, event)

    def showMap(self):
        # Simple function to show the buffer mapping window
        self.mapWindow.open()

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("You need to have a document open to use this script!")
            return
        # Check layer map validity before doing anything
        try:
            self.mapWindow.validateMapping()
        except Exception as e:
            self.errBox.setPlainText(f"Layer mapping is invalid, click Map Buffers and fix:\n{e.args[0]}")
            return
        newNodes = []
        inputTextures = []
        program = None
        outFrameBuffer = None
        vao = None
        # Must specify this context otherwise Krita will cause issues if using OpenGL for main renderer
        with self.ext.ctx as ctx:
            # Create a shader program from the text boxes
            try:
                program = ctx.program(
                    vertex_shader=self.vertBox.toPlainText(),
                    fragment_shader=self.fragBox.toPlainText())
            except Exception as e:
                # Failure here means likely no OGL objects to clean up
                self.errBox.setPlainText(str(e))
                if program:
                    program.release()
                return
            # Map inputs from the input mapper
            for input in self.mapWindow.inputTextureMapItems:
                # Get node this item references
                if input.layerId == "<>":
                    node = doc.activeNode()
                else:
                    node = doc.nodeByUniqueID(QUuid(input.layerId))
                # Get color format data from the node
                components, colorType = self.getColorComponentsAndType(node)
                # Create input texture from current layer
                inputTexture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorType)
                # Set up some attributes for the input texture
                inputTexture.repeat_x = input.repeat
                inputTexture.repeat_y = input.repeat
                # This is to fix RGBA color mode actually being BGRA with integer color depth
                if self.rgbaCorrectCheck.isChecked():
                    self.rgbaColorCorrector.swizzleTextureIfNeeded(node, inputTexture)
                inputTextures.append(inputTexture)
                # Attempt to bind the textures to the program and texture units and assign samplers
                try:
                    inputTexture.use(location=input.index)
                    if input.variableName:
                        program[input.variableName] = input.index
                except Exception as e:
                    self.errBox.setPlainText(str(e))
                    # Cleanup and early exit
                    for i in inputTextures:
                        i.release()
                    program.release()
                    return
            outputTextures = []
            # Create output textures with information from the mapper
            for output in self.mapWindow.outputTextureMapItems:
                if output.layerId == "<>":
                    # Special case for new layer
                    # TODO: Should there be a way to specify different color formats?
                    node = doc
                    components, colorType = self.getColorComponentsAndType(node)
                    outputTexture = ctx.texture((doc.width(), doc.height()), components, dtype=colorType)
                else:
                    node = doc.nodeByUniqueID(QUuid(output.layerId))
                    components, colorType = self.getColorComponentsAndType(node)
                    # Copy the pixel data to the texture, in case it doesn't all get overwritten
                    outputTexture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorType)
                outputTexture.repeat_x = output.repeat
                outputTexture.repeat_y = output.repeat
                if self.rgbaCorrectCheck.isChecked():
                    self.rgbaColorCorrector.fixTextureIfNeeded(node, outputTexture)
                outputTextures.append(outputTexture)
            # Attempt to create and bind the framebuffer
            try:
                # Create framebuffer with all output textures
                outFrameBuffer = ctx.framebuffer(outputTextures)
                outFrameBuffer.use() # Bind the framebuffer to the program
                vao = ctx.vertex_array(program, [])
            except Exception as e:
                self.errBox.setPlainText(str(e))
                # Cleanup and early exit
                for i in inputTextures:
                    i.release()
                for o in outputTextures:
                    o.release()
                if outFrameBuffer:
                    outFrameBuffer.release()
                if vao:
                    vao.release()
                program.release()
                return
            try:
                vertices = int(self.vertNumber.text())
                if vertices != -1:
                    vao.vertices = vertices
                # Set the primitive drawing mode
                match self.vertMode.currentIndex():
                    case 0:
                        vao.mode = ctx.POINTS
                    case 1:
                        vao.mode = ctx.LINES
                    case 2:
                        vao.mode = ctx.LINE_LOOP
                    case 3:
                        vao.mode = ctx.LINE_STRIP
                    case 4:
                        vao.mode = ctx.TRIANGLES
                    case 5:
                        vao.mode = ctx.TRIANGLE_STRIP
                    case 6:
                        vao.mode = ctx.TRIANGLE_FAN
                    case _:
                        vao.mode = ctx.TRIANGLES
            except ValueError as e:
                # Could not parse number of vertices, good luck
                pass
            
            ctx.clear()
            # Display any errors in warningWidget
            try:
                vao.render()
                ctx.finish()
                # Run the RGBA channel correction pass if needed
                if self.rgbaCorrectCheck.isChecked():
                    self.rgbaColorCorrector.renderCorrectionIfNeeded(ctx, doc)
                # Copy data from output buffers to nodes
                for index in range(len(self.mapWindow.outputTextureMapItems)):
                    output = self.mapWindow.outputTextureMapItems[index]
                    if output.layerId == "<>":
                        # Put the result into a new node
                        # TODO: If output color format differs from document, this new node's color format needs to be changed to match
                        node = doc.createNode(f"Render Result {index}", "paintlayer")
                        newNodes.append(node)
                    else:
                        node = doc.nodeByUniqueID(QUuid(output.layerId))
                    # If this output needed color channel correction, use the corrected texture
                    textureToUse = outputTextures[index] if not (self.rgbaCorrectCheck.isChecked() and self.rgbaColorCorrector.nodeNeedsCorrection(node)) else self.rgbaColorCorrector.getNextCorrectedTexture()
                    node.setPixelData(textureToUse.read(), 0, 0, doc.width(), doc.height())
                self.errBox.setPlainText("")
            except Exception as e:
                self.errBox.setPlainText(str(e))
            # Cleanup
            for i in inputTextures:
                i.release()
            for o in outputTextures:
                o.release()
            outFrameBuffer.release()
            vao.release()
            program.release()
            self.rgbaColorCorrector.cleanUp()
        # Exit the context scope before adding new nodes
        for newNode in newNodes:
            doc.activeNode().parentNode().addChildNode(newNode, doc.activeNode())
        doc.refreshProjection()
        self.saveSettings()

    def getColorComponentsAndType(self, node):
        # Helper function to get the number of components and data type from a node
        colorModel = node.colorModel()
        # Number of components is the number of capitals in the color model, unless GRAYA
        if colorModel == "GRAYA":
            components = 2
        else:
            components = sum(1 for c in colorModel if c.isupper())
        colorDepth = node.colorDepth()
        colorDepth = colorDepth[0].lower() + str(int(colorDepth[1:]) // 8)
        return components, colorDepth

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Render Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL vertex and fragment shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://learnopengl.com has good tutorials. Here are some more useful bits of info:

   > No vertices are fed into the vertex shader from the program, you will need to define your own vertices inside the shader to render.
   > Use the text box above the vertex shader to specify how many vertices are to be processed.
   > Change the primitive draw mode using the selection box next to the box to specify the number of vertices.
   > Input and output textures can be configured using the Map Buffers button.
   > By default, the active layer is the input, and the output will be added to a new layer above the active layer.
   > Varyings output from the vertex shader can be used as inputs to the fragment shader.
   > Fix RGBA color channel order option will try to ensure colors are in the correct channels, else red and blue could be swapped.
   > There is no syntax highlighting, it is advisable you use some other editor to make the shaders.
   > Shader files can be saved and loaded using Save and Open, selecting a vertex shader first then a fragment shader.""")
        self.helpWindow.open()

    def openFile(self):
        # Because this has two shaders to save, this will open two different dialogs
        # Open a file selection dialog
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Vertex Shaders (*.vert)")
        # Load the selected shaders into the text boxes
        if file[0]:
            with open(file[0], 'r') as vf:
                self.vertBox.setPlainText(vf.read())
        # Open a file selection dialog for the next shader
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Fragment Shaders (*.frag)")
        if file[0]:
            with open(file[0], 'r') as ff:
                self.fragBox.setPlainText(ff.read())

    def saveFile(self):
        # This will also open two dialogs to save the two different shaders
        # Open a file save dialog
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Vertex Shaders (*.vert)")
        # Write the contents of the text box to file
        if file[0]:
            with open(file[0], 'w') as vf:
                vf.write(self.vertBox.toPlainText())
        # Open a file save dialog for the second shader
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Fragment Shaders (*.frag)")
        if file[0]:
            with open(file[0], 'w') as ff:
                ff.write(self.fragBox.toPlainText())

    def saveAndReject(self):
        self.saveSettings()
        self.reject()

    def closeEvent(self, event):
        self.saveSettings()
        event.accept()

    def saveSettings(self):
        rect = QRect(
            self.geometry().x() - self.geometryDelta.x(),
            self.geometry().y() - self.geometryDelta.y(),
            self.geometry().width() - self.geometryDelta.width(),
            self.geometry().height() - self.geometryDelta.height())
        self.ext.settings.setValue("mgl_geometry", rect)
        self.ext.settings.setValue("mgl_vert_number", self.vertNumber.text())
        self.ext.settings.setValue("mgl_vert_mode", self.vertMode.currentIndex())
        self.ext.settings.setValue("mgl_frag_rgba_fix", self.rgbaCorrectCheck.isChecked())
        if self.vertBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_vert_shader", self.vertBox.toPlainText())
        if self.fragBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_frag_shader", self.fragBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        self.readGeometry = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(self.readGeometry)
        self.vertNumber.setText(self.ext.settings.value("mgl_vert_number", "-1"))
        self.vertMode.setCurrentIndex(int(self.ext.settings.value("mgl_vert_mode", "4")))
        self.rgbaCorrectCheck.setChecked(self.ext.settings.value("mgl_frag_rgba_fix", "true") == "true")
        self.vertBox.setPlainText(self.ext.settings.value("mgl_vert_shader", ""))
        self.fragBox.setPlainText(self.ext.settings.value("mgl_frag_shader", ""))