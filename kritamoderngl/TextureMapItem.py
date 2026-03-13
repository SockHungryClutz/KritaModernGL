# Utility/data class for handling mapping layers to textures for input and output
class TextureMapItem():
    layerId: str
    read: bool
    write: bool
    index: int
    repeat: bool
    variableName: str

    # Initialize from individual components or a dict from a JSON string
    def __init__(self, layerId:str="", read:bool=True, write:bool=False, index:int=0, repeat:bool=True, variableName:str="", json:dict=None):
        if json:
            self.layerId = json['layerId']
            self.read = json['read']
            self.write = json['write']
            self.index = json['index']
            self.repeat = json['repeat']
            self.variableName = json['variableName']
        else:
            self.layerId = layerId
            self.read = read
            self.write = write
            self.index = index
            self.repeat = repeat
            self.variableName = variableName
    
    # Print as a JSON object
    def __str__(self):
        return f'{{"layerId":"{self.layerId}","read":{str(self.read).lower()},"write":{str(self.write).lower()},"index":{self.index},"repeat":{str(self.repeat).lower()},"variableName":"{self.variableName}"}}'

    # Other string method should also print as a JSON object
    def __repr__(self):
        return f'{{"layerId":"{self.layerId}","read":{str(self.read).lower()},"write":{str(self.write).lower()},"index":{self.index},"repeat":{str(self.repeat).lower()},"variableName":"{self.variableName}"}}'

    # define < method for sorting by index
    def __lt__(self, other):
        return self.index < other.index