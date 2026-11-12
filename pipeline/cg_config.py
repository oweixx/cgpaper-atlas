"""User-approved scope: four conference series and four journals."""
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CACHE = ROOT / '.cache' / 'cg'
YEAR = datetime.now(timezone.utc).year
VENUES = {
 'SIGGRAPH': {'name':'ACM SIGGRAPH','stream':'conf/siggraph','kind':'conference','since':1974,'color':'#2563eb','labels':['SIGGRAPH','SIGGRAPH (Conference Paper Track)','ACM Trans. Graph.']},
 'SIGGRAPH Asia': {'name':'ACM SIGGRAPH Asia','stream':'conf/siggrapha','kind':'conference','since':2008,'color':'#7c3aed','labels':['SIGGRAPH Asia','ACM Trans. Graph.']},
 'Eurographics': {'name':'Eurographics','stream':'conf/eurographics','kind':'conference','since':1980,'color':'#08916d','labels':['Eurographics','Comput. Graph. Forum']},
 'Pacific Graphics': {'name':'Pacific Graphics','stream':'conf/pg','kind':'conference','since':1993,'color':'#d97706','labels':['PG','Comput. Graph. Forum','Vis. Comput.']},
 'TOG': {'name':'ACM Transactions on Graphics','stream':'journals/tog','kind':'journal','since':1982,'color':'#dc4b61','issn':'0730-0301'},
 'CGF': {'name':'Computer Graphics Forum','stream':'journals/cgf','kind':'journal','since':1982,'color':'#0891b2','issn':'0167-7055'},
 'TVCG': {'name':'IEEE Transactions on Visualization and Computer Graphics','stream':'journals/tvcg','kind':'journal','since':1995,'color':'#8b6a43','issn':'1077-2626'},
 'C&G': {'name':'Computers & Graphics','stream':'journals/cg','kind':'journal','since':1975,'color':'#a3458c','issn':'0097-8493'},
}
