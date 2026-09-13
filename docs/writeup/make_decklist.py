import csv, sys, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
src, out = sys.argv[1], sys.argv[2]
rows=list(csv.DictReader(open(src)))
groups=[("Pokémon (13)",[r for r in rows if r['category'].startswith('Pokémon (')]),
        ("Trainers — Items & Tools (19)",[r for r in rows if r['category'] in ('Item','Pokémon Tool')]),
        ("Trainers — Supporters (13)",[r for r in rows if r['category']=='Supporter']),
        ("Stadiums (3)",[r for r in rows if r['category'].startswith('Stadium')]),
        ("Energy (12)",[r for r in rows if 'Energy' in r['category']])]
for g,rs in groups: assert sum(int(r['count']) for r in rs)==int(g.split('(')[1].rstrip(')')), (g, sum(int(r['count']) for r in rs))
roles={'Great Tusk':'mill engine (Land Collapse; 4 cards with an Ancient Supporter) / attack-plan finisher','Dwebble':'self-thinning wall line','Crustle':'wall: ex attacks deal 0 (Mysterious Rock Inn); Superb Scissors 120 ignores effects','Budew':'turn-2 Item lock when going second',
 'Poké Pad':'consistency','Bug Catching Set':'second thinning line','Crushing Hammer':'energy denial (2, not 4: each Item is a card not milling)','Pokégear 3.0':'Supporter search','Jumbo Ice Cream':'heal 80 — buys Crustle a turn vs Munkidori transfers','Switch':'tempo / Budew line','Buddy-Buddy Poffin':'Basic search','Night Stretcher':'recovery','Counter Gain':'cheaper Giant Tusk when behind on Prizes',
 "Explorer's Guidance":'Ancient Supporter: turns Land Collapse into a 4-card mill; draw second',"Lillie's Determination":'draw',"Boss's Orders":'KO this turn, or remove a Basic before it grows',"Xerosic's Machinations":'trim hand to 3 before Enhanced Hammers line up',
 'Neutralization Zone':'ACE SPEC: no damage from ex/V attacks to non-Rule-Box Pokémon','Battle Cage':'blocks bench-damage Abilities',
 'Basic Grass Energy':'Crustle / Great Tusk','Rock Fighting Energy':'anti-Alakazam; cancels attack effects; attached just-in-time','Mist Energy':'anti-Alakazam effect immunity; attached just-in-time'}
fig,ax=plt.subplots(figsize=(9.5,9.4),dpi=160); ax.axis('off')
y=0.985; ax.text(0.0,y,"Great Tusk / Crustle deck-out — final submission (60 cards)",fontsize=13,fontweight='bold',va='top'); y-=0.045
for g,rs in groups:
    ax.text(0.0,y,g,fontsize=10.5,fontweight='bold',color='#1f4e79',va='top'); y-=0.028
    for r in sorted(rs,key=lambda r:-int(r['count'])):
        ax.text(0.02,y,f"{r['count']}×",fontsize=9.5,va='top',family='monospace'); ax.text(0.07,y,r['card'],fontsize=9.5,va='top',fontweight='bold')
        ax.text(0.34,y,roles.get(r['card'],r['note']),fontsize=8.5,va='top',color='#333'); y-=0.024
    y-=0.012
ax.text(0.0,0.005,"Card names are Pokémon Elements of The Pokémon Company, cited as permitted by the competition rules.",fontsize=7,color='#777',va='bottom')
fig.savefig(out,bbox_inches='tight'); print('saved', out)
