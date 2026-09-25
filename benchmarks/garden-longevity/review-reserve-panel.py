"""Verify frozen policy bundles and export derived aggregates/pairs; never rerun a policy."""
import argparse
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT = Path('artifacts')
DAY = 3840


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_bundle(path):
    manifest = json.loads((path/'manifest.json').read_text())
    assert manifest['status'] == 'complete'
    for name,sha in manifest['artifacts'].items():
        assert digest(path/name) == sha, name
    return manifest


def aggregate(cases, day):
    closing, post, totals = Counter(), Counter(), Counter()
    for c in cases:
        m = c['milestones'][str(day*DAY)]
        p = m['population']
        for prefix in ('closing','post_establishment'):
            cohort = m[prefix]
            assert cohort['offspring_born'] == (cohort['eligible_offspring']+
                cohort['recent_alive']+cohort['recent_dead'])
            assert 0 <= cohort['cycle_survivors_with_surviving_child'] <= cohort['cycle_survivors'] <= cohort['eligible_offspring']
        assert p['extinct'] == (p['living']==0 and p['seeds']==0)
        closing.update(m['closing'])
        post.update(m['post_establishment'])
        totals.update({k:p[k] for k in ('living','seeds','births','deaths','nodes','living_genotypes')})
        totals.update(extinct=int(p['extinct']), families=len(p['extant_families']),
            species=len(p['extant_species']), single_species=int(len(p['extant_species'])==1),
            single_family=int(len(p['extant_families'])==1),
            closing_natural_deaths=m['closing_natural_deaths'],
            closing_environmental_deaths=m['closing_environmental_deaths'],
            with_closing_births=int(m['closing']['offspring_born']>0),
            with_closing_survivors=int(m['closing']['cycle_survivors']>0),
            with_closing_durable=int(m['closing']['cycle_survivors_with_surviving_child']>0))
    soil = [c['soil_final'] for c in cases]
    return {'runs':len(cases), 'closing':closing, 'post':post, 'totals':totals,
        'soil_day192':{'min':min(soil), 'max':max(soil), 'mean':sum(soil)/len(soil)}}


def paired(cases):
    pairs = []
    for old in cases:
        if old['policy'] != 'neural':
            continue
        new = next(c for c in cases if c['id']==old['id'] and c['arm']==old['arm']
            and c['setting']==old['setting'] and c['policy']=='reserve')
        a,b = old['milestones'][str(192*DAY)],new['milestones'][str(192*DAY)]
        x,y = a['population'],b['population']
        d = {f'{prefix}_{k}':b[prefix][k]-a[prefix][k] for prefix in ('closing','post_establishment')
            for k in a[prefix]}
        d.update({k:y[k]-x[k] for k in ('living','seeds','births','living_genotypes','nodes')})
        d.update(families=len(y['extant_families'])-len(x['extant_families']),
            species=len(y['extant_species'])-len(x['extant_species']),
            soil_final=new['soil_final']-old['soil_final'])
        pairs.append({'id':old['id'],'scenario':old['scenario'],'seed':old['seed'],'arm':old['arm'],
            'setting':old['setting'],'delta':d,'baseline_extinct':x['extinct'],'reserve_extinct':y['extinct'],
            'baseline_closing':a['closing'],'reserve_closing':b['closing']})
    return pairs


def collect():
    output = {'bundles':{}, 'aggregates':[], 'paired':[], 'checks':{}}
    baseline_cohort_checks = 0
    for capacity in (256,512):
        path = ROOT/f'garden-reserve-panel-{capacity}'
        manifest = verified_bundle(path)
        assert manifest['panel']=='full' and manifest['expected_runs']==320 and manifest['node_capacity']==capacity
        cases = json.loads((path/'cases.json').read_text())
        assert len(cases)==320
        baseline = ROOT/f'garden-bottom-drainage-{capacity}'
        bm = json.loads((baseline/'manifest.json').read_text())
        assert bm['status']=='complete' and digest(baseline/'manifest.json')==manifest['baseline_manifest_sha256']
        assert digest(baseline/'summary.json')==bm['artifacts']['summary.json']
        bs = json.loads((baseline/'summary.json').read_text())
        for setting in ('off','on'):
            for arm in ('control','fresh-1','fresh-2','fresh-3','fresh-4'):
                for day in (64,128,192):
                    current = aggregate([c for c in cases if c['policy']=='neural'
                        and c['setting']==setting and c['arm']==arm],day)
                    old = bs[setting]['population'][arm]['milestones'][str(day)]
                    assert current['closing']==old['closing']
                    assert current['post']==old['post_establishment']
                    baseline_cohort_checks += 2
        output['bundles'][str(capacity)] = {'manifest_sha256':digest(path/'manifest.json'),
            'artifact_count':len(manifest['artifacts']), 'source_count':len(manifest['source_sha256'])}
        for scenario in ('all','rainfed','rainfed-crowded'):
            for group in ('control','disturbed'):
                for setting in ('off','on'):
                    selected = [c for c in cases if (scenario=='all' or c['scenario']==scenario)
                        and (c['arm']=='control')==(group=='control') and c['setting']==setting]
                    for day in (64,128,192):
                        for policy in ('neural','reserve'):
                            subset = [c for c in selected if c['policy']==policy]
                            output['aggregates'].append({'capacity':capacity,'scenario':scenario,'group':group,
                                'setting':setting,'policy':policy,'day':day,**aggregate(subset,day)})
        output['paired'].extend({'capacity':capacity,**pair} for pair in paired(cases))
    prior = ROOT/'garden-reserve-growth'
    verified_bundle(prior)
    count = 0
    for old in (prior/'analyses').glob('*.population.json'):
        new = ROOT/'garden-reserve-panel-512'/'analyses'/old.name
        assert json.loads(old.read_text())==json.loads(new.read_text()), old.name
        count += 1
    assert count == 40
    output['checks']['prior_focused_exact_analyses'] = count
    output['checks']['baseline_aggregate_cohort_checks'] = baseline_cohort_checks
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='New JSON output; omit to print to stdout')
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error('Output already exists; choose a new file')
    report = json.dumps(collect(),sort_keys=True,indent=2)+'\n'
    if args.output is None:
        print(report,end='')
    else:
        with args.output.open('x') as stream:
            stream.write(report)
        print(f'Verified both completed bundles; wrote {args.output}')
