// Modèle de site/config.js : copier ce fichier dans site/config.js et y mettre
// l'identifiant secret du webhook Home Assistant (le même que dans l'automatisation
// homeassistant/liste-de-courses.yaml). site/config.js n'est pas suivi par git ;
// il doit être déployé à côté de site/index.html.
// Générer un identifiant : python3 -c "import secrets; print(secrets.token_urlsafe(18))"
window.RECETTES_CONFIG = {
  haWebhook: "https://homeassistant.d.perivol.net/api/webhook/recettes-courses-CHANGEZ-MOI"
};
