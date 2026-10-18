"""Configuration commune des tests.

Locale neutre : les messages testés sont les chaînes source (anglais). Sans ce
réglage, un runner en locale française (LANGUAGE/LANG=fr_FR) applique le
catalogue lang/fr_FR et les assertions sur « Import failed », « corrupted »…
échouent selon la machine qui exécute la CI. ``LANGUAGE=C`` désactive les
traductions pour Python (gettext lit LANGUAGE en premier) comme pour GNU gettext.
Les tests de traduction gardent la main : ils posent leur propre LANGUAGE avec
``monkeypatch.setenv`` ou dans l'environnement du sous-processus.
"""

import os

os.environ["LANGUAGE"] = "C"
