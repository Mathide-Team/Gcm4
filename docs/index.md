# Gcm4

Gcm4 est le gestionnaire de connexions multi-protocoles de Mathide-Team, un
fork de [Gnome Connection Manager](https://github.com/kuthulux/gnome-connection-manager).
Il regroupe dans une seule fenêtre à onglets les accès distants : terminal
SSH, bureau RDP, console série RS-232/485, VNC, SPICE, telnet, session
locale, console BMC IPMI SOL et visualiseur web BMC. Chaque protocole est
un plugin chargé au démarrage. L'application est en cours de migration de
GTK3 vers GTK4.

## Par où commencer

- **Utiliser Gcm4** : la [documentation utilisateur](guide/utilisateur.md),
  puis le [fichier de configuration](configuration.md).
- **Changer de langue** : [Langue de l'interface](i18n.md).
- **Un problème** : [Journaux et mode debug](journalisation.md).
- **Contribuer** : l'[architecture](architecture.md), puis
  [écrire un plugin](plugins.md) et la [migration GTK4](gtk4-migration.md).
- **Ce qui reste à faire** : la [roadmap](roadmap.md) et le
  [backlog](features-backlog.md).

Le README du dépôt (installation, packaging deb/rpm, écosystème des
bibliothèques asynchrones) reste la référence pour l'installation :
[README sur GitHub](https://github.com/Mathide-Team/Gcm4/blob/dev/README.md).
