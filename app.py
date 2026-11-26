from flask import Flask, render_template, request, redirect, url_for, flash, Response
from dataclasses import dataclass, asdict
import json, os, logging, csv, io
from pathlib import Path
from functools import wraps

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'nutrition_records.json'

@dataclass
class NutritionRecord:
    id: int
    name: str
    category: str
    serving_size: float
    calories: float
    protein: float
    carbs: float
    fat: float
    sodium: float

class NutritionManager:
    def __init__(self, filename=DATA_FILE):
        self.filename = Path(filename)
        self.records = []
        self.load_data()

    def load_data(self):
        try:
            if self.filename.exists():
                with self.filename.open(encoding='utf-8') as f:
                    raw = json.load(f)
                self.records = [NutritionRecord(**item) for item in raw]
            else:
                self.records = []
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logging.exception('Could not load nutrition records: %s', exc)
            self.records = []

    def save_data(self):
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        temp = self.filename.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in self.records], f, indent=2)
        temp.replace(self.filename)

    def all(self):
        return sorted(self.records, key=lambda r: r.name.lower())

    def get(self, record_id):
        return next((r for r in self.records if r.id == record_id), None)

    def add(self, data):
        new_id = max((r.id for r in self.records), default=0) + 1
        record = NutritionRecord(id=new_id, **data)
        self.records.append(record)
        self.save_data()
        return record

    def update(self, record_id, data):
        record = self.get(record_id)
        if record is None: return False
        for key, value in data.items(): setattr(record, key, value)
        self.save_data()
        return True

    def delete(self, record_id):
        before = len(self.records)
        self.records = [r for r in self.records if r.id != record_id]
        if len(self.records) != before: self.save_data(); return True
        return False

    def search(self, query='', category=''):
        q, c = query.lower().strip(), category.lower().strip()
        return [r for r in self.all() if q in r.name.lower() and (not c or c in r.category.lower())]

    def compare(self, id1, id2):
        return self.get(id1), self.get(id2)

manager = NutritionManager()
if not manager.records:
    manager.records = [
        NutritionRecord(1, 'Greek Yogurt (Plain)', 'Dairy', 170, 100, 18, 6, 0.4, 60),
        NutritionRecord(2, 'Almonds (Roasted)', 'Snacks', 28, 164, 6, 6, 14, 1),
        NutritionRecord(3, 'Oatmeal (Prepared)', 'Grains', 240, 150, 5, 27, 2.5, 105),
        NutritionRecord(4, 'Chicken Breast (Grilled)', 'Protein', 100, 165, 31, 0, 3.6, 74),
        NutritionRecord(5, 'Bread', 'Snacks', 2, 0.3, 0.8, 4, 2, 0.6),
        NutritionRecord(6, 'Chicken', 'Lunch', 200, 15, 24, 150, 50, 345),
    ]
    manager.save_data()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-change-this-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Simple per-session CSRF token via Flask session
from flask import session
import secrets
@app.before_request
def csrf_setup():
    session.setdefault('csrf_token', secrets.token_hex(24))

def csrf_protect(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if request.method == 'POST' and request.form.get('csrf_token') != session.get('csrf_token'):
            flash('Security token mismatch. Please retry.', 'error')
            return redirect(url_for('index'))
        return fn(*args, **kwargs)
    return wrapped

def get_form_data():
    name = request.form.get('name','').strip()
    category = request.form.get('category','').strip()
    if not name or not category or len(name) > 100 or len(category) > 60:
        raise ValueError('Name and category are required and must be within length limits.')
    fields = {}
    bounds = {'serving_size': (0.1, 5000), 'calories': (0, 5000), 'protein': (0, 500), 'carbs': (0, 500), 'fat': (0, 500), 'sodium': (0, 10000)}
    for field, (low, high) in bounds.items():
        try: value = float(request.form.get(field, ''))
        except (TypeError, ValueError): raise ValueError(f'{field.replace("_", " ").title()} must be a number.')
        if not (low <= value <= high): raise ValueError(f'{field.replace("_", " ").title()} must be between {low} and {high}.')
        fields[field] = value
    return {'name': name, 'category': category, **fields}

@app.route('/')
def index():
    records = manager.all()
    total = len(records)
    averages = {key: round(sum(getattr(r, key) for r in records)/total, 2) if total else 0 for key in ['calories','protein','carbs','fat','sodium']}
    categories = {}
    for r in records: categories[r.category] = categories.get(r.category, 0) + 1
    charts = {'labels':[r.name for r in records], 'calories':[r.calories for r in records], 'protein':[r.protein for r in records], 'carbs':[r.carbs for r in records], 'fat':[r.fat for r in records], 'sodium':[r.sodium for r in records], 'category_labels':list(categories), 'category_values':list(categories.values())}
    top_protein = max(records, key=lambda r:r.protein) if records else None
    return render_template('index.html', records=records, averages=averages, charts=charts, top_protein=top_protein, token=session['csrf_token'])

@app.route('/products')
def products():
    query=request.args.get('q',''); category=request.args.get('category','')
    return render_template('products.html', records=manager.search(query,category), categories=sorted(set(r.category for r in manager.records)), query=query, category=category, token=session['csrf_token'])

@app.route('/add', methods=['GET','POST'])
@csrf_protect
def add():
    if request.method=='POST':
        try: manager.add(get_form_data()); flash('Product added successfully.', 'success'); return redirect(url_for('products'))
        except ValueError as e: flash(str(e), 'error')
    return render_template('form.html', record=None, token=session['csrf_token'])

@app.route('/edit/<int:record_id>', methods=['GET','POST'])
@csrf_protect
def edit(record_id):
    record=manager.get(record_id)
    if not record: flash('Product not found.', 'error'); return redirect(url_for('products'))
    if request.method=='POST':
        try: manager.update(record_id,get_form_data()); flash('Product updated.', 'success'); return redirect(url_for('products'))
        except ValueError as e: flash(str(e), 'error')
    return render_template('form.html', record=record, token=session['csrf_token'])

@app.route('/delete/<int:record_id>', methods=['POST'])
@csrf_protect
def delete(record_id):
    manager.delete(record_id); flash('Product removed.', 'success'); return redirect(url_for('products'))

@app.route('/compare')
def compare():
    records=manager.all(); id1=request.args.get('a',type=int); id2=request.args.get('b',type=int)
    p1,p2=manager.compare(id1,id2) if id1 and id2 else (None,None)
    return render_template('compare.html', records=records, p1=p1,p2=p2)

@app.route('/export')
def export():
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(['ID','Name','Category','Serving Size','Calories','Protein','Carbs','Fat','Sodium'])
    for r in manager.all(): writer.writerow([r.id,r.name,r.category,r.serving_size,r.calories,r.protein,r.carbs,r.fat,r.sodium])
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=nutrition_export.csv'})

if __name__ == '__main__':
    app.run(debug=False)
