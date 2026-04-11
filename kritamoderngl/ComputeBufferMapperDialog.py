from krita import *
from PyQt5.QtCore import Qt, QRect, QUuid
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QDialog, QFileDialog, QDialogButtonBox, QComboBox, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QPushButton
import json
from . import TextureMapItem

# Dialog box to configure input and output buffers for the compute shader dialog
class ComputeBufferMapperDialog(QDialog):
    def __init__(self, parent=None):
        super(ComputeBufferMapperDialog, self).__init__(parent)
        self.imageMapItems = []
        self.textureMapItems = []
        
        self.helpWindow = QMessageBox(parent=self)
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open |
            QDialogButtonBox.Save |
            QDialogButtonBox.Reset |
            QDialogButtonBox.Apply |
            QDialogButtonBox.Help |
            QDialogButtonBox.Cancel,
            self)
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.openFile)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveFile)
        self.buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.resetMap)
        self.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.applyChanges)
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        self.setWindowModality(Qt.WindowModal)
        
        self.mapLabel = QLabel("Image Unit Mapping:", self)
        self.createLayerLists()
        self.imageMap = QTableWidget(len(self.imageMapItems), 5, self)
        self.imageMap.setHorizontalHeaderLabels(["Image Unit Index", "Target Layer", "Read", "Write", "Repeat"])
        self.imageMap.setCornerButtonEnabled(False)
        self.imageMap.verticalHeader().setVisible(False)
        orderUp = QPushButton(Krita.instance().icon("arrow-up"), "Move Up")
        orderUp.clicked.connect(self.moveRowUp)
        orderDown = QPushButton(Krita.instance().icon("arrow-down"), "Move Down")
        orderDown.clicked.connect(self.moveRowDown)
        listAdd = QPushButton(Krita.instance().icon("list-add"), "Add")
        listAdd.clicked.connect(self.addRow)
        listRemove = QPushButton(Krita.instance().icon("list-remove"), "Remove")
        listRemove.clicked.connect(self.removeRow)
        self.mapEditBox = QHBoxLayout()
        self.mapEditBox.addWidget(orderUp)
        self.mapEditBox.addWidget(orderDown)
        self.mapEditBox.addWidget(listAdd)
        self.mapEditBox.addWidget(listRemove)
        
        self.texMapLabel = QLabel("Texture Unit Mapping:", self)
        self.textureMap = QTableWidget(len(self.textureMapItems), 4, self)
        self.textureMap.setHorizontalHeaderLabels(["Texture Unit Index", "Target Layer", "Repeat", "Sampler Name"])
        self.textureMap.setCornerButtonEnabled(False)
        self.textureMap.verticalHeader().setVisible(False)
        texOrderUp = QPushButton(Krita.instance().icon("arrow-up"), "Move Up")
        texOrderUp.clicked.connect(self.moveTexRowUp)
        texOrderDown = QPushButton(Krita.instance().icon("arrow-down"), "Move Down")
        texOrderDown.clicked.connect(self.moveTexRowDown)
        texListAdd = QPushButton(Krita.instance().icon("list-add"), "Add")
        texListAdd.clicked.connect(self.addTexRow)
        texListRemove = QPushButton(Krita.instance().icon("list-remove"), "Remove")
        texListRemove.clicked.connect(self.removeTexRow)
        self.texMapEditBox = QHBoxLayout()
        self.texMapEditBox.addWidget(texOrderUp)
        self.texMapEditBox.addWidget(texOrderDown)
        self.texMapEditBox.addWidget(texListAdd)
        self.texMapEditBox.addWidget(texListRemove)
        self.readSettings()
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.mapLabel)
        vbox.addWidget(self.imageMap)
        vbox.addLayout(self.mapEditBox)
        vbox.addWidget(self.texMapLabel)
        vbox.addWidget(self.textureMap)
        vbox.addLayout(self.texMapEditBox)
        vbox.addWidget(self.buttonBox)
        
        self.setWindowTitle("Configure Input and Output Buffers")
        self.setSizeGripEnabled(False)

    def showEvent(self, event):
        # This will undo any changes from last time the window was shown and update the layer list drop down
        self.createLayerLists()
        self.readSettings()

    def updateView(self):
        # Updates the UI to reflect changes made to the data model
        self.imageMap.setRowCount(len(self.imageMapItems))
        for idx in range(len(self.imageMapItems)):
            # Create the widgets and items that will populate the cells
            indexWidget = QTableWidgetItem(str(idx))
            indexWidget.setFlags(indexWidget.flags() ^ Qt.ItemIsEditable)
            indexWidget.setToolTip("Image Unit Index.\nThis must be in order, change by reordering rows.")
            layerWidget = QComboBox()
            layerWidget.addItems(["", "<ACTIVE LAYER>", "<NEW LAYER>"] + self.nameList)
            layerWidget.setInsertPolicy(QComboBox.NoInsert)
            layerWidget.setToolTip("Choose layer in current document to sample from.\n<ACTIVE LAYER> will sample the currently selected layer.\n<NEW LAYER> will add a layer above the current layer.")
            try:
                layerWidget.setCurrentIndex(self.uuidList.index(self.imageMapItems[idx].layerId))
            except ValueError:
                layerWidget.setCurrentIndex(0)
            readWidget = QCheckBox()
            readWidget.setChecked(self.imageMapItems[idx].read)
            readWidget.setToolTip("Set whether the image is readable (input).")
            writeWidget = QCheckBox()
            writeWidget.setChecked(self.imageMapItems[idx].write)
            writeWidget.setToolTip("Set whether the image is writable (output).")
            repeatWidget = QCheckBox()
            repeatWidget.setChecked(self.imageMapItems[idx].repeat)
            repeatWidget.setToolTip("Set whether the texture repeats when sampling beyond the bounds.")
            # Assign the widgets to cells
            self.imageMap.setItem(idx, 0, indexWidget)
            self.imageMap.setCellWidget(idx, 1, layerWidget)
            self.imageMap.setCellWidget(idx, 2, readWidget)
            self.imageMap.setCellWidget(idx, 3, writeWidget)
            self.imageMap.setCellWidget(idx, 4, repeatWidget)

    def updateTexView(self):
        # Updates the texture mapping UI to reflect changes made to the data models
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)
        self.textureMap.setRowCount(len(self.textureMapItems))
        for idx in range(len(self.textureMapItems)):
            # Create the widgets and items that will populate the cells
            indexWidget = QTableWidgetItem(str(idx))
            indexWidget.setFlags(indexWidget.flags() ^ Qt.ItemIsEditable)
            indexWidget.setToolTip("Texture Unit Index.\nThis must be in order, change by reordering rows.")
            layerWidget = QComboBox()
            layerWidget.addItems(["", "<ACTIVE LAYER>"] + self.nameList)
            layerWidget.setInsertPolicy(QComboBox.NoInsert)
            layerWidget.setToolTip("Choose layer in current document to sample from.\n<ACTIVE LAYER> will sample the currently selected layer.")
            try:
                uuidIdx = self.uuidList.index(self.textureMapItems[idx].layerId)
                # This will skip over "new layer" in the index list
                if uuidIdx >= 2:
                    uuidIdx -= 1
                layerWidget.setCurrentIndex(uuidIdx)
            except ValueError:
                layerWidget.setCurrentIndex(0)
            repeatWidget = QCheckBox()
            repeatWidget.setChecked(self.textureMapItems[idx].repeat)
            repeatWidget.setToolTip("Set whether the texture repeats when sampling beyond the bounds.")
            samplerWidget = QTableWidgetItem()
            samplerWidget.setFont(monoFont)
            samplerWidget.setToolTip("Set the name of the sampler to map to in the fragment shader.")
            if self.textureMapItems[idx].variableName: samplerWidget.setText(self.textureMapItems[idx].variableName)
            # Assign the widgets to cells
            self.textureMap.setItem(idx, 0, indexWidget)
            self.textureMap.setCellWidget(idx, 1, layerWidget)
            self.textureMap.setCellWidget(idx, 2, repeatWidget)
            self.textureMap.setItem(idx, 3, samplerWidget)

    def updateModel(self):
        # Updates the image list data to reflect changes made in the UI view
        self.imageMapItems = []
        for idx in range(self.imageMap.rowCount()):
            mapItem = TextureMapItem.TextureMapItem(self.uuidList[self.imageMap.cellWidget(idx, 1).currentIndex()],
                                                    self.imageMap.cellWidget(idx, 2).isChecked(),
                                                    self.imageMap.cellWidget(idx, 3).isChecked(),
                                                    idx,
                                                    self.imageMap.cellWidget(idx, 4).isChecked(),
                                                    "")
            self.imageMapItems.append(mapItem)

    def updateTexModel(self):
        # Updates the texture list data to reflect changes made in the UI view
        self.textureMapItems = []
        for idx in range(self.textureMap.rowCount()):
            uuidIdx = self.textureMap.cellWidget(idx, 1).currentIndex()
            if uuidIdx > 1:
                uuidIdx += 1
            mapItem = TextureMapItem.TextureMapItem(self.uuidList[uuidIdx],
                                                    True,
                                                    False,
                                                    idx,
                                                    self.textureMap.cellWidget(idx, 2).isChecked(),
                                                    self.textureMap.item(idx, 3).text())
            self.textureMapItems.append(mapItem)

    def validateMapping(self):
        # Checks if the mapping is valid, throws an exception with description if invalid, nothing otherwise
        self.updateModel()
        for item in self.imageMapItems:
            # All inputs and outputs need a valid target layer
            if item.layerId == "":
                raise Exception(f"Invalid Configuration\nImage unit at index {item.index}\nTarget Layer cannot be null.")
            # All Outputs must map to a paintlayer node
            if item.write and item.layerId != "<>" and item.layerId != "<2>":
                layerType = Krita.instance().activeDocument().nodeByUniqueID(QUuid(item.layerId)).type()
                if layerType != "paintlayer" and layerType[-4:] != "mask":
                    raise Exception(f"Invalid Configuration\nImage unit at index {item.index}\nOutputs must target paintable layers (type={layerType}).")
            # No inputs can be mapped to new layer
            if item.read and item.layerId == "<2>":
                raise Exception(f"Invalid Configuration\nImage unit at index {item.index}\nInputs cannot target new layers.")
        self.updateTexModel()
        for item in self.textureMapItems:
            # All textures need a valid target layer
            if item.layerId == "":
                raise Exception(f"Invalid Configuration\nTexture unit at index {item.index}\nTarget Layer cannot be null.")
            # Should not happen, but just being safe
            if item.layerId == "<2>":
                raise Exception(f"Invalid Configuration\nTexture unit at index {item.index}\nInputs cannot target new layers.")
        return True

    def getSelectedRows(self, table, reverse=False):
        # Helper function to get the currently selected rows on the input buffer table
        # Find which cells are selected and get their rows
        selectedRows = []
        for idx in table.selectedIndexes():
            if idx.row() not in selectedRows:
                selectedRows.append(idx.row())
        selectedRows.sort(reverse=reverse)
        return selectedRows

    def moveRowUp(self):
        # Move the current selected rows up if able
        # Ensure the model is currently up-to-date
        self.updateModel()
        selectedRows = self.getSelectedRows(self.imageMap)
        # Row 0 cannot be moved up, so it and any rows in sequence after are invalid and skipped
        invalidRow = 0
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow += 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows up one position from front to back
        for row in selectedRows:
            self.imageMapItems = self.imageMapItems[:row-1] \
                                   + [self.imageMapItems[row]] \
                                   + [self.imageMapItems[row-1]] \
                                   + self.imageMapItems[row+1:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.imageMapItems)):
            self.imageMapItems[idx].index = idx
        # Update view for texture unit map
        self.updateView()

    def moveTexRowUp(self):
        # Move the current selected rows up if able
        # Ensure the model is currently up-to-date
        self.updateTexModel()
        selectedRows = self.getSelectedRows(self.textureMap)
        # Row 0 cannot be moved up, so it and any rows in sequence after are invalid and skipped
        invalidRow = 0
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow += 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows up one position from front to back
        for row in selectedRows:
            self.textureMapItems = self.textureMapItems[:row-1] \
                                    + [self.textureMapItems[row]] \
                                    + [self.textureMapItems[row-1]] \
                                    + self.textureMapItems[row+1:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.textureMapItems)):
            self.textureMapItems[idx].index = idx
        # Update view for input map
        self.updateTexView()

    def moveRowDown(self):
        # Move the current selected rows down if able
        # Ensure the model is currently up-to-date
        self.updateModel()
        selectedRows = self.getSelectedRows(self.imageMap, reverse=True)
        # Last row cannot be moved down, so it and any rows in sequence before are invalid and skipped
        invalidRow = len(self.imageMapItems) - 1
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow -= 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows down one position from back to front
        for row in selectedRows:
            self.imageMapItems = self.imageMapItems[:row] \
                                        + [self.imageMapItems[row+1]] \
                                        + [self.imageMapItems[row]] \
                                        + self.imageMapItems[row+2:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.imageMapItems)):
            self.imageMapItems[idx].index = idx
        # Update view for texture unit map
        self.updateView()

    def moveTexRowDown(self):
        # Move the current selected rows down if able
        # Ensure the model is currently up-to-date
        self.updateTexModel()
        selectedRows = self.getSelectedRows(self.textureMap, reverse=True)
        # Last row cannot be moved down, so it and any rows in sequence before are invalid and skipped
        invalidRow = len(self.textureMapItems) - 1
        while selectedRows and selectedRows[0] == invalidRow:
            selectedRows = selectedRows[1:]
            invalidRow -= 1
        # Quick check to see if there is any work to do
        if not selectedRows: return
        # Shuffle all selected rows down one position from back to front
        for row in selectedRows:
            self.textureMapItems = self.textureMapItems[:row] \
                                        + [self.textureMapItems[row+1]] \
                                        + [self.textureMapItems[row]] \
                                        + self.textureMapItems[row+2:]
        # Remap the indexes of all items in the list
        for idx in range(len(self.textureMapItems)):
            self.textureMapItems[idx].index = idx
        # Update view for input map
        self.updateTexView()

    def addRow(self):
        # Add a new row with default values below the current row, or at the bottom if none are selected
        # Ensure the model is currently up-to-date
        self.updateModel()
        # If multiple rows are selected, place a new entry below the lowest selected row
        selectedRows = self.getSelectedRows(self.imageMap, reverse=True)
        newEntry = TextureMapItem.TextureMapItem("<>")
        if selectedRows:
            self.imageMapItems.insert(selectedRows[0]+1, newEntry)
        else:
            self.imageMapItems.append(newEntry)
        self.updateView()

    def addTexRow(self):
        # Add a new row with default values below the current row, or at the bottom if none are selected
        # Ensure the model is currently up-to-date
        self.updateTexModel()
        # If multiple rows are selected, place a new entry below the lowest selected row
        selectedRows = self.getSelectedRows(self.textureMap, reverse=True)
        newEntry = TextureMapItem.TextureMapItem("<>")
        if selectedRows:
            self.textureMapItems.insert(selectedRows[0]+1, newEntry)
        else:
            self.textureMapItems.append(newEntry)
        self.updateTexView()

    def removeRow(self):
        # Remove the current selected rows from the table
        # Ensure the model is currently up-to-date
        self.updateModel()
        # Removing is easy working back to front
        selectedRows = self.getSelectedRows(self.imageMap, reverse=True)
        for row in selectedRows:
            del self.imageMapItems[row]
        self.updateView()

    def removeTexRow(self):
        # Remove the current selected rows from the table
        # Ensure the model is currently up-to-date
        self.updateTexModel()
        # Removing is easy working back to front
        selectedRows = self.getSelectedRows(self.textureMap, reverse=True)
        for row in selectedRows:
            del self.textureMapItems[row]
        self.updateTexView()

    def resetMap(self):
        self.imageMapItems = [TextureMapItem.TextureMapItem("<2>", False, True), TextureMapItem.TextureMapItem("<>")]
        self.textureMapItems = []
        self.updateView()
        self.updateTexView()

    def applyChanges(self):
        try:
            self.validateMapping()
            self.saveSettings()
            self.accept()
        except Exception as e:
            self.helpWindow.setText("Configuration Warning")
            self.helpWindow.setInformativeText(e.args[0])
            self.helpWindow.open()

    def showHelp(self):
        self.helpWindow.setText("Texture Unit Mapping")
        self.helpWindow.setInformativeText("""This window is for manually mapping texture units for compute shader inputs and outputs.

   > Texture units can be bound to texture image2D uniforms using `layout (binding = <INDEX>, <FORMAT>)`.
   > All inputs and outputs must be set to a valid layer in the document, outputs must be assigned to a paintlayer or mask layer.
   > The Repeat option sets whether the layer used as the texture will repeat when sampling beyond the texture bounds.
   > Textures can be mapped to be used in samplers, these can only be used as inputs.
   > Press Reset at any time to reset the inputs and outputs to default values.
   > If you like to poke around, the configuration is saved as JSON. If you break something, delete the mgl_map_comp_texture_map entry in krita-scripterrc and restart Krita.""")
        self.helpWindow.open()

    def openFile(self):
        # Open a file selection dialog
        file = QFileDialog.getOpenFileName(
            self,
            "Select a file to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "JSON File (*.json)")
        if file[0]:
            with open(file[0], 'r') as f:
                jsonMap = json.loads(f.read())
                self.imageMapItems = []
                self.textureMapItems = []
                try:
                    # This is for back compatability, if exception is raised then fallback to old method
                    thing = jsonMap[0][0]
                    for item in jsonMap[0]:
                        self.imageMapItems.append(TextureMapItem.TextureMapItem(json=item))
                    for item in jsonMap[1]:
                        self.textureMapItems.append(TextureMapItem.TextureMapItem(json=item))
                except Exception:
                    for item in jsonMap:
                        self.imageMapItems.append(TextureMapItem.TextureMapItem(json=item))
                self.updateView()
                self.updateTexView()

    def saveFile(self):
        # Open a file save dialog
        self.updateModel()
        self.updateTexModel()
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "JSON File (*.json)")
        if file[0]:
            with open(file[0], 'w') as f:
                self.updateModel()
                f.write(str([self.imageMapItems, self.textureMapItems]))

    def saveAndReject(self):
        self.saveSettings(False)
        self.reject()

    def closeEvent(self, event):
        self.saveSettings(False)
        event.accept()

    def saveSettings(self, saveMaps=True):
        if saveMaps:
            self.updateModel()
            self.updateTexModel()
        rect = QRect(
            self.geometry().x(),
            self.geometry().y(),
            1, 1) # width and height do not matter
        self.parentWidget().ext.settings.setValue("mgl_map_comp_geometry", rect)
        if saveMaps:
            self.parentWidget().ext.settings.setValue("mgl_map_comp_texture_map", str(self.imageMapItems))
            self.parentWidget().ext.settings.setValue("mgl_map_comp_texture_map2", str(self.textureMapItems))
        self.parentWidget().ext.settings.sync()

    def readSettings(self):
        readGeometry = self.parentWidget().ext.settings.value("mgl_map_comp_geometry", None)
        if readGeometry != None:
            self.move(readGeometry.x(), readGeometry.y())
        default = '[{"layerId":"<2>","read":false,"write":true,"index":0,"repeat":true,"variableName":""},{"layerId":"<>","read":true,"write":false,"index":1,"repeat":true,"variableName":""}]'
        jsonMap = json.loads(self.parentWidget().ext.settings.value("mgl_map_comp_texture_map", default))
        jsonMap2 = json.loads(self.parentWidget().ext.settings.value("mgl_map_comp_texture_map2", "[]"))
        self.imageMapItems = []
        self.textureMapItems = []
        for item in jsonMap:
            self.imageMapItems.append(TextureMapItem.TextureMapItem(json=item))
        for item in jsonMap2:
            self.textureMapItems.append(TextureMapItem.TextureMapItem(json=item))
        self.updateView()
        self.updateTexView()

    def createLayerLists(self):
        # Assume this will work because you need an active document to open the shader plugin
        nodes = Krita.instance().activeDocument().topLevelNodes()
        nameList = []
        uuidList = []
        for node in nodes:
            name, uuid = listNodesRecursive(nameList, uuidList, node)
            nameList.insert(0, name)
            uuidList.insert(0, uuid)
        self.nameList = nameList
        self.uuidList = ["", "<>", "<2>"] + uuidList

# Helper function to recursively list all nodes in the document
def listNodesRecursive(names, uuids, node, prefix="  "):
    children = node.childNodes()
    for child in children:
        name, uuid = listNodesRecursive(names, uuids, child, "  " + prefix)
        names.insert(0, prefix + name)
        uuids.insert(0, prefix + uuid)
    return node.name(), node.uniqueId().toString()