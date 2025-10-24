from flask import Flask, render_template, make_response, redirect, url_for, request, jsonify,session, flash, send_file, make_response
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import current_app

import zipfile
import tempfile
import base64
import requests
# from weasyprint import HTML
import os
import uuid

from mysql.connector import Error
from config import DB_CONFIG

import random

from flask import session


from io import BytesIO


app = Flask(__name__)

app.secret_key = "a4s4powerful"  # Clé secrète pour gérer les sessions


UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---- Fonction utilitaire pour sauvegarder les fichiers ----
def save_file(field_name):
    f = request.files.get(field_name)
    if f and f.filename:
        filename = f"{uuid.uuid4()}_{secure_filename(f.filename)}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(path)
        return filename
    return None

# Connexion à la base de données MySQL
def connect_db():
    return mysql.connector.connect(**DB_CONFIG)

@app.context_processor
def inject_nom_etablissement():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT nom_etablissement FROM etablissement LIMIT 1")
    row = cur.fetchone()
    conn.close()
    nom_etablissement = row['nom_etablissement'] if row else "Nom de l'École"
    
    return dict(nom_etablissement=nom_etablissement)

@app.context_processor
def inject_recrutement_actif():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT verification_actif FROM configuration WHERE id = 1")
    actif = cur.fetchone()['verification_actif']
    conn.close()
    return dict(verification_actif=actif)


# ----------------------- AUTHENTIFICATION ------------------------

# ---- Route d'accueil ----
@app.route('/')
def index():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)

    # Récupérer toutes les professions
    cur.execute("SELECT * FROM professions")
    professions = cur.fetchall()

    # Récupérer toutes les offres
    cur.execute("SELECT * FROM offres")
    offres = cur.fetchall()

    conn.close()

    # Année actuelle pour le footer
    from datetime import datetime
    current_year = datetime.now().year

    return render_template('index.html', professions=professions, offres=offres, current_year=current_year)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = connect_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_nom'] = user['nom']
            session['user_role'] = user['role']

            return redirect(url_for('dashboard'))
        flash("Email ou mot de passe incorrect", "danger")
    return render_template('login.html')

# ----------------------- CREATION COMPTE UTILISATEUR ------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    # Récupérer toutes les classes pour les afficher dans le formulaire


    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        
        cur.execute("INSERT INTO users (nom, email, password, role) VALUES (%s, %s, %s, %s)", 
                    (nom, email, password, role))
        conn.commit()
        conn.close()
        flash("Inscription réussie", "success")
        return redirect(url_for('login'))
    return render_template('register.html')


# ----------------------- PROFIL UTILISATEUR ------------------------
@app.route('/profil', methods=['GET', 'POST'])
def profil():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT nom, email FROM users WHERE id = %s", (session['user_id'],))
    user = cur.fetchone()

    if request.method == 'POST':
        nom = request.form['nom']
        email = request.form['email']
        password = request.form['password']

        if password:
            hashed = generate_password_hash(password)
            cur.execute("UPDATE users SET nom=%s, email=%s, password=%s WHERE id=%s", (nom, email, hashed, session['user_id']))
        else:
            cur.execute("UPDATE users SET nom=%s, email=%s WHERE id=%s", (nom, email, session['user_id']))

        conn.commit()
        flash("Profil mis à jour avec succès", "success")
        return redirect(url_for('login'))

    return render_template('profil.html', user=user)


# ----------------------- SUPPRIMER UN COMPTE UTILISATEUR ------------------------

@app.route('/supprimer_compte', methods=['POST'])
def supprimer_compte():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM users WHERE id = %s", (session['user_id'],))
    conn.commit()

    session.clear()
    flash("Compte supprimé avec succès", "success")
    return redirect(url_for('login'))

# ----------------------- DECONNEXION ------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ----------------------- Dashboard ------------------------
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = connect_db()
    cur = conn.cursor(dictionary=True)

    # Infos de l'établissement
    cur.execute("SELECT nom_etablissement, lieu, adresse, commune, province, code, annee_scolaire FROM etablissement LIMIT 1")
    etab = cur.fetchone()

    etablissement = {
        'nom': etab['nom_etablissement'],
        'lieu': etab['lieu'],
        'adresse': etab['adresse'],
        'commune': etab['commune'],
        'province': etab['province'],
        'code': etab['code'],
        'annee_scolaire': etab['annee_scolaire']
    }

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        actif = 1 if 'verification_actif' in request.form else 0
        cur.execute("UPDATE configuration SET verification_actif = %s WHERE id = 1", (actif,))
        conn.commit()
        flash("État de recrutement mis à jour avec succès.", "success")

    return render_template('dashboard.html', etablissement=etablissement)


# ----------------------- CRUD: ETABLISSEMENT ------------------------

@app.route('/etablissement')
def gestion_etablissement():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM etablissement")
    etablissements = cur.fetchall()
    conn.commit()

    conn.close()
    return render_template("gestion_etablissement.html", etablissements=etablissements)


@app.route('/add_etablissement', methods=['POST'])
def add_etablissement():
    nom_etablissement = request.form['nom_etablissement']
    lieu = request.form['lieu']
    adresse = request.form['adresse']
    commune = request.form['commune']
    province = request.form['province']
    code = request.form['code']
    annee_scolaire = request.form['annee_scolaire']
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("INSERT INTO etablissement (nom_etablissement, lieu, adresse, commune, province, code, annee_scolaire) VALUES (%s, %s, %s, %s, %s, %s, %s)", (nom_etablissement, lieu, adresse, commune, province, code, annee_scolaire,))
    conn.commit()
    conn.close()
    return redirect(url_for('gestion_etablissement'))


@app.route('/delete_etablissement/<int:id>')
def delete_etablissement(id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM etablissement WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('gestion_etablissement'))


@app.route('/edit_etablissement/<int:id>', methods=['GET', 'POST'])
def edit_etablissement(id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        nom_etablissement = request.form['nom_etablissement']
        lieu = request.form['lieu']
        adresse = request.form['adresse']
        commune = request.form['commune']
        province = request.form['province']
        code = request.form['code']
        annee_scolaire = request.form['annee_scolaire']
        cur.execute("UPDATE etablissement SET nom_etablissement = %s, lieu = %s, adresse = %s, commune = %s, province = %s, code = %s, annee_scolaire = %s WHERE id = %s", (nom_etablissement, lieu, adresse, commune, province, code, annee_scolaire, id))
        conn.commit()
        conn.close()
        return redirect(url_for('gestion_etablissement'))

    cur.execute("SELECT * FROM etablissement WHERE id = %s", (id,))
    etablissement = cur.fetchone()
    conn.commit()


    col_names = [desc[0] for desc in cur.description]

    conn.close()
    return render_template("edit_etablissement.html", etablissement=etablissement)

# ----------------------- GESTION DES CANDIDATS ------------------------

# ---- Route d'inscription candidat ----
@app.route('/inscription_candidat', methods=['GET', 'POST'])
def inscription_candidat():
    if request.method == 'POST':
        nom = request.form['nom']
        postnom = request.form['postnom']
        prenom = request.form['prenom']
        email = request.form['email']
        date_naissance = request.form['date_naissance']
        sexe = request.form['sexe']
        etat_civil = request.form['etat_civil']
        nom_conjoint = request.form.get('nom_conjoint') or None
        adresse = request.form['adresse']
        telephone = request.form['telephone']
        allergies = request.form.get('allergies')
        offre_id = request.form['offre_id']
        profession_id = request.form['profession_id']

        # Photo
        photo_file = request.files.get('photo')
        photo_filename = save_file('photo') if photo_file else None

        # Pièces jointes
        carte_electeur = save_file('carte_electeur')
        cv = save_file('cv')

        conn = connect_db()
        cur = conn.cursor()

        # Vérifier doublon (nom + postnom + prenom + email)
        cur.execute("""
            SELECT id FROM candidats WHERE nom=%s AND postnom=%s AND prenom=%s AND email=%s AND offre_id=%s AND profession_id=%s
        """, (nom, postnom, prenom, email, offre_id, profession_id))
        if cur.fetchone():
            conn.close()
            flash("Ce candidat existe déjà.", "danger")
            return redirect(url_for('index'))

        # Insertion
        cur.execute("""
            INSERT INTO candidats (
                nom, postnom, prenom, email, date_naissance, sexe, etat_civil, nom_conjoint,
                adresse, telephone, photo, allergies, offre_id, profession_id,
                carte_electeur, cv
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            nom, postnom, prenom, email, date_naissance, sexe, etat_civil, nom_conjoint,
            adresse, telephone, photo_filename, allergies, offre_id, profession_id,
            carte_electeur, cv
        ))
        conn.commit()
        conn.close()

        flash("Candidature envoyée avec succès.", "success")
        return redirect(url_for('index'))

    # GET → afficher formulaire

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, titre, profession_id FROM offres")
    offres = cur.fetchall()
    cur.execute("SELECT * FROM professions")
    professions = cur.fetchall()
    conn.close()
    return render_template('inscription_candidat.html', offres=offres, professions=professions)


@app.route('/candidats')
def liste_candidats():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    
    # Récupérer les candidats avec leurs offres et professions
    cur.execute("""
        SELECT c.*, o.titre AS offre, p.nom AS profession
        FROM candidats c
        JOIN offres o ON c.offre_id = o.id
        JOIN professions p ON c.profession_id = p.id
        ORDER BY c.date_enregistrement DESC
    """)
    candidats = cur.fetchall()
    
    # Récupérer toutes les offres pour les <select>
    cur.execute("SELECT * FROM offres")
    offres = cur.fetchall()
    
    # Récupérer toutes les professions pour les <select>
    cur.execute("SELECT * FROM professions")
    professions = cur.fetchall()
    
    conn.close()
    
    return render_template('manage_candidats.html',
                           candidats=candidats,
                           offres=offres,
                           professions=professions)



# ---- Route pour modifier un candidat ----
@app.route('/modifier_candidat/<int:id>', methods=['POST'])
def modifier_candidat(id):
    nom = request.form['nom']
    postnom = request.form['postnom']
    prenom = request.form['prenom']
    email = request.form['email']
    date_naissance = request.form['date_naissance']
    sexe = request.form['sexe']
    etat_civil = request.form['etat_civil']
    nom_conjoint = request.form.get('nom_conjoint') or None
    adresse = request.form['adresse']
    telephone = request.form['telephone']
    allergies = request.form.get('allergies')
    offre_id = request.form['offre_id']
    profession_id = request.form['profession_id']

    # Photo
    photo_file = request.files.get('photo')
    photo_filename = save_file('photo') if photo_file and photo_file.filename else None

    conn = connect_db()
    cur = conn.cursor()

    # Vérifier doublon pour un autre candidat (même nom, postnom, prenom, email)
    cur.execute("""
        SELECT id FROM candidats WHERE nom=%s AND postnom=%s AND prenom=%s AND email=%s AND id != %s
    """, (nom, postnom, prenom, email, id))
    if cur.fetchone():
        conn.close()
        flash("Un autre candidat avec ces informations existe déjà.", "danger")
        return redirect(url_for('liste_candidats'))

    # Construire la requête UPDATE
    if photo_filename:
        cur.execute("""
            UPDATE candidats SET
                nom=%s, postnom=%s, prenom=%s, email=%s,
                date_naissance=%s, sexe=%s, etat_civil=%s, nom_conjoint=%s,
                adresse=%s, telephone=%s, allergies=%s,
                offre_id=%s, profession_id=%s, photo=%s
            WHERE id=%s
        """, (
            nom, postnom, prenom, email,
            date_naissance, sexe, etat_civil, nom_conjoint,
            adresse, telephone, allergies,
            offre_id, profession_id, photo_filename, id
        ))
    else:
        # Si aucune nouvelle photo, ne pas modifier le champ photo
        cur.execute("""
            UPDATE candidats SET
                nom=%s, postnom=%s, prenom=%s, email=%s,
                date_naissance=%s, sexe=%s, etat_civil=%s, nom_conjoint=%s,
                adresse=%s, telephone=%s, allergies=%s,
                offre_id=%s, profession_id=%s
            WHERE id=%s
        """, (
            nom, postnom, prenom, email,
            date_naissance, sexe, etat_civil, nom_conjoint,
            adresse, telephone, allergies,
            offre_id, profession_id, id
        ))

    conn.commit()
    conn.close()

    flash("Candidat mis à jour avec succès.", "success")
    return redirect(url_for('liste_candidats'))


# ---- Suppression ----
@app.route('/candidats/delete/<int:id>')
def delete_candidat(id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM candidats WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("Candidat supprimé avec succès.", "info")
    return redirect(url_for('liste_candidats'))


# ---- Voir documents d'un candidat ----
@app.route('/candidats/documents/<int:candidat_id>')
def voir_documents_candidat(candidat_id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM candidats WHERE id=%s", (candidat_id,))
    candidat = cur.fetchone()
    conn.close()

    if not candidat:
        flash("Candidat introuvable.", "danger")
        return redirect(url_for('liste_candidats'))

    return render_template('documents_candidat.html', candidat=candidat)


# ---- Télécharger tous les documents d'un candidat ----
@app.route('/candidats/documents/telecharger/<int:candidat_id>')
def telecharger_documents_candidat(candidat_id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM candidats WHERE id=%s", (candidat_id,))
    candidat = cur.fetchone()
    conn.close()

    if not candidat:
        flash("Candidat introuvable.", "danger")
        return redirect(url_for('liste_candidats'))

    # Créer un ZIP en mémoire
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for label, doc in {
            "CV": candidat['cv'],
            "Carte_electeur": candidat['carte_electeur']
        }.items():
            if doc:
                path = os.path.join('static/uploads', doc)
                zf.write(path, arcname=f"{label}_{doc}")
    memory_file.seek(0)

    return send_file(memory_file, download_name=f"Documents_{candidat['nom']}_{candidat['prenom']}.zip", as_attachment=True)


# ----------------------- GESTION DES PROFESSIONS ------------------------

@app.route('/manage_professions')
def manage_professions():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM professions")
    professions = cur.fetchall()
    return render_template('manage_professions.html', professions=professions)


@app.route('/add_profession', methods=['POST'])
def add_profession():
    nom = request.form['nom']
    description = request.form['description']

    # Photo obligatoire pour une profession
    photo_file = request.files.get('photo')
    photo_filename = None
    if photo_file and photo_file.filename:
        photo_filename = secure_filename(photo_file.filename)
        photo_file.save(os.path.join('static/uploads', photo_filename))

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("INSERT INTO professions (nom, description, photo) VALUES (%s, %s, %s)",
                (nom, description, photo_filename))
    conn.commit()
    return redirect(url_for('manage_professions'))


@app.route('/update_profession/<int:id>', methods=['POST'])
def update_profession(id):
    nom = request.form['nom']
    description = request.form['description']

    photo_file = request.files.get('photo')
    photo_filename = None

    conn = connect_db()
    cur = conn.cursor(dictionary=True)

    if photo_file and photo_file.filename:
        photo_filename = secure_filename(photo_file.filename)
        photo_file.save(os.path.join('static/uploads', photo_filename))
    else:
        cur.execute("SELECT photo FROM professions WHERE id=%s", (id,))
        result = cur.fetchone()
        if result:
            photo_filename = result['photo']

    # Mise à jour
    cur.execute(
        "UPDATE professions SET nom=%s, description=%s, photo=%s WHERE id=%s",
        (nom, description, photo_filename, id)
    )
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('manage_professions'))



@app.route('/delete_profession/<int:id>')
def delete_profession(id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM professions WHERE id=%s", (id,))
    conn.commit()
    return redirect(url_for('manage_professions'))


# ----------------------- GESTION DES OFFRES D'EMPLOI ------------------------

@app.route('/manage_offres')
def manage_offres():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT offres.id, offres.titre, offres.description, professions.nom AS profession
        FROM offres
        JOIN professions ON offres.profession_id = professions.id
    """)
    offres = cur.fetchall()

    cur.execute("SELECT * FROM professions")
    professions = cur.fetchall()

    return render_template('manage_offres.html', offres=offres, professions=professions)


@app.route('/add_offre', methods=['POST'])
def add_offre():
    titre = request.form['titre']
    description = request.form['description']
    profession_id = request.form['profession_id']

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("INSERT INTO offres (titre, description, profession_id) VALUES (%s, %s, %s)",
                (titre, description, profession_id))
    conn.commit()
    return redirect(url_for('manage_offres'))


@app.route('/update_offre/<int:id>', methods=['POST'])
def update_offre(id):
    titre = request.form['titre']
    description = request.form['description']
    profession_id = request.form['profession_id']

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("UPDATE offres SET titre=%s, description=%s, profession_id=%s WHERE id=%s",
                (titre, description, profession_id, id))
    conn.commit()
    return redirect(url_for('manage_offres'))


@app.route('/delete_offre/<int:id>')
def delete_offre(id):
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM offres WHERE id=%s", (id,))
    conn.commit()
    return redirect(url_for('manage_offres'))


# ----------------------- RUN ------------------------

if __name__ == '__main__':
    app.run(debug=True)