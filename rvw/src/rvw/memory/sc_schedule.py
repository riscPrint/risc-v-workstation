"""Bounded SC scheduling for greedy dead ends. Failure proves nothing."""


def schedule(harts, initial, limit=20000):
    ids=sorted(harts)
    # Positions, memory source identities and live LR sources determine a state.
    latest={key:f'initial:{key[0]}:{key[1]}' for key in initial}
    stack=[(dict.fromkeys(ids,0),dict(initial),latest,{},[],[],[])]
    seen=set()
    branches=0
    total=sum(map(len,harts.values()))
    while stack and branches<limit:
        positions,state,latest,reservations,order,co,rf=stack.pop()
        signature=(tuple(positions[h] for h in ids),tuple(sorted(latest.items())),tuple(sorted(reservations.items())))
        if signature in seen: continue
        seen.add(signature);branches+=1
        if len(order)==total:
            return dict(global_order=order,co=co,rf=rf,
                        certificate='sequential consistency; co contains adjacent edges',
                        scheduling_branches=branches)
        ready=[]
        for h in ids:
            if positions[h]==len(harts[h]): continue
            e=harts[h][positions[h]];kind=e['kind'];key=(e.get('address'),e.get('size'))
            if kind in ('R','LR','AMO') and state[key]!=e['read']: continue
            if kind=='SC' and reservations.get(e['rmw'])!=latest[key]: continue
            ready.append((h,e,key))
        # Try reads before conflicting overwrites. This is only search order.
        ready.sort(key=lambda item:(item[1]['kind'] not in ('R','LR'),item[0]))
        for h,e,key in reversed(ready):
            kind=e['kind'];pos=dict(positions);values=dict(state);sources=dict(latest);lr=dict(reservations)
            next_co=co;next_rf=rf
            if kind in ('R','LR','AMO'): next_rf=rf+[(latest[key],e['id'])]
            if kind=='LR': lr[e['id']]=latest[key]
            if kind in ('W','SC','AMO'):
                next_co=co+[(latest[key],e['id'])]
                sources[key]=e['id'];values[key]=e['write']
            pos[h]+=1
            stack.append((pos,values,sources,lr,order+[e['id']],next_co,next_rf))
    return None
