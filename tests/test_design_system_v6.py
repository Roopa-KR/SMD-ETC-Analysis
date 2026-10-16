"""v6: presentation and link smoke tests; no operational formula changes."""
from pathlib import Path
import re
import pytest

@pytest.fixture(scope='module')
def client():
    from app import app
    return app.test_client()

@pytest.mark.parametrize('path,title,section', [
    ('/?snapshot=10', 'Dashboard', 'Truck performance'),
    ('/planner?snapshot=10&worktype=2', 'Workforce allocation', 'Available experienced operators'),
    ('/operators?snapshot=10', 'Operators', 'Operator directory'),
    ('/truck/SH0908-1034?snapshot=10', 'SH0908-1034', 'Truck ready time: before vs after adding operators'),
    ('/operator/hgroff?snapshot=10', 'Operator hgroff', 'Work-type familiarity'),
])
def test_every_page_uses_shared_shell_and_real_sections(client,path,title,section):
    res=client.get(path)
    assert res.status_code==200
    html=res.get_data(as_text=True)
    for text in ('id="app-sidebar"', 'id="sidebar-toggle"', 'id="header-snapshot"',
                 'id="main-content"', 'style.css', 'bootstrap.min.css',
                 'bootstrap.bundle.min.js'):
        assert text in html
    assert title in html
    assert section in html
    assert 'http://127.0.0.1' not in html

@pytest.mark.parametrize('path',[
    '/planner?snapshot=10&worktype=2', '/operators?snapshot=10',
    '/truck/SH0908-1034?snapshot=10', '/operator/hgroff?snapshot=10'
])
def test_interior_pages_use_shared_headings_and_white_cards(client,path):
    html=client.get(path).get_data(as_text=True)
    assert 'interior-intro' in html
    assert 'surface-card' in html
    assert 'risk-badge' in html or 'stat-card' in html


def test_supervisor_forms_retained_and_selection_not_allocation(client):
    from app import supervisor_scenario
    html=client.get('/planner?snapshot=10&worktype=2').get_data(as_text=True)
    for action in ('loading','add'):
        assert f'value="{action}"' in html
    template=(Path(__file__).resolve().parents[1]/'templates/planner.html').read_text()
    for action in ('clear','allocate','reset_scenario'):
        assert f'value="{action}"' in template
    for text in ('data-candidate-search','planner-data',
                 'No transfer time is modeled','Source',
                 'risk inherited from the relevant truck/worktype'):
        assert text.casefold() in html.casefold()
    assert 'data-confirm-allocation' not in html  # no candidate preview selected yet


def test_direct_links_and_usable_local_static_assets(client):
    for asset in ('/static/css/style.css','/static/js/planner.js',
                  '/static/js/ready_chart.js','/static/js/shell.js',
                  '/static/vendor/bootstrap.min.css','/static/vendor/bootstrap.bundle.min.js'):
        response=client.get(asset)
        assert response.status_code == 200
        assert len(response.data)>100
    html=client.get('/operators?snapshot=10').get_data(as_text=True)
    assert 'data-directory-search' in html
    assert '/operator/hgroff?snapshot=10' in html
    assert client.get('/export/trucks.csv?snapshot=10').status_code==200


def test_templates_preserve_original_plot_data_and_business_routes(client):
    html=client.get('/truck/SH0908-1034?snapshot=10').get_data(as_text=True)
    assert 'id="ready-chart-data"' in html and 'ready_chart.js' in html  # v10 shared chart
    assert 'automatically suggested reallocation is disabled' in html
    html=client.get('/planner?snapshot=10&worktype=2').get_data(as_text=True)
    assert 'Before allocation' in html and 'id="planner-ready-chart-data"' in html  # v10
    assert 'SH0908-1034' in html
    assert 'every truck there must stay on time' in html
    assert '10-minute safety buffer' in client.get('/?snapshot=10').get_data(as_text=True).lower()
