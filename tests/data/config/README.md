# Fixtures de configuration (#138)

`gcm.conf` anonymisées au format de `Wmain.writeConfig`, chiffrées par les
fonctions de l'application GTK3 (`gcm4_core.encrypt` / `encrypt_old`)
pour l'utilisateur `utilisateur` :

- `aes/` : format courant (`[options] version = 1`), avec sa `.gcm.key` ;
- `ancien/` : ancien format XOR (pas de `version`), sans `.gcm.key`.

Mots de passe en clair (tests uniquement) : `api` → `Mot2Passe!é`,
`web` → vide, `db` → `s3cr3t-très-long-pour-plusieurs-blocs-AES-0123456789`.
Groupes imbriqués, couleurs, champs de deux protocoles, groupe vide et
section de plugin inconnue.
