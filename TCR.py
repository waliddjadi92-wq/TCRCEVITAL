import streamlit as st
import pandas as pd
import json
from io import BytesIO

###############################################################################
#                         MODULE DE TRAITEMENT TCR                             #
###############################################################################

def to_numeric_safe(x):
    """Convertit proprement les valeurs en numérique."""
    try:
        s = str(x).replace('\xa0','').replace(' ', '').replace(',', '.')
        return float(s) if s not in ('nan', 'None', '') else 0.0
    except:
        return 0.0

def df_to_poste_value_map_manual(mapping):
    """Récupère les valeurs saisies manuellement dans le mapping."""
    postes = {}
    for key, field_name in mapping.items():
        value = st.number_input(f"{key}", value=0.0, step=1.0)
        postes[key] = to_numeric_safe(value)
    return postes

# ================== MAPPING PAR DÉFAUT ==================
DEFAULT_MAPPING = {
    "CHIFFRE D'AFFAIRES H.T.": "CA_HT",
    "Dont exportations": "CA_export",
    "Dont ventes de marchandises": "CA_ventes_marchandises",
    "Production Vendue": "Prod_vendue",
    "Production stockée": "Prod_stockee",
    "Production immobilisée": "Prod_immobilisee",
    "Prestations fournies": "Prestations",
    "Autres produits d'exploitation": "Autres_prod_expl",
    "Achats": "Achats",
    "Variation de stock matières, marchandises": "Variation_stock",
    "Autres charges externes (hors crédit bail, intérim)": "Charges_externes",
    "dont sous-traitance": "Sous_traitance",
    "Variation prov. d'exploitation, transfert charges de Prod": "Variation_prov_expl_transf",
    "Frais de personnel": "Frais_personnel",
    "Impôts et taxes": "Impots_taxes",
    "Frais divers": "Frais_divers",
    "Produits divers": "Produits_divers",
    "Transfert de Charge d'Exploitation": "Transf_charge_expl",
    "Autres produits d'Exploitation": "Autres_prod_expl_2",
    "Dotations aux amortissements": "Dotations_amortissements",
    "Dotations aux provisions": "Dotations_provisions",
    "Part en capital des loyers de crédit bail": "Part_capital_loyers_credit_bail",
    "Loyers d'actifs d'exploitation": "Loyers_actifs_expl",
    "Solde sur opérations faites en commun": "Solde_operations_communes",
    "Produits financiers": "Produits_financiers",
    "Frais financiers": "Frais_financiers",
    "Solde de change et autres": "Solde_change_autres",
    "Charges et produits sans effet sur la MBA": "Charges_produits_sans_effet",
    "± values sur cessions, reprise subv. invest.": "Plus_minus_cessions",
    "Variation provisions pr dépr. d'immo. Financières": "Variation_prov_immo_fin",
    "Variation des provisions réglementées": "Variation_prov_reglementees",
    "Autres produits et charges exceptionnels": "Autres_prod_charges_exceptionnels",
    "Provisions exceptionnelles pour risques & charges": "Provisions_exceptionnelles",
    "Participation des salariés": "Participation_salaries",
    "Impôts sur les bénéfices": "Impots_benefices",
    "RESULTAT NET COMPTABLE": "RNC_explicite"
}

# ===================== CALCUL DES AGRÉGATS ======================
def compute_tcr_aggregates(postes_map, mapping=None):
    if mapping is None:
        mapping = DEFAULT_MAPPING

    # normaliser
    norm_values = {}
    for raw, val in postes_map.items():
        key = mapping.get(raw, "Autres_generaux")
        norm_values[key] = norm_values.get(key, 0.0) + float(val)

    get = lambda k: float(norm_values.get(k, 0.0))

    PRODUITS_EXPLOITATION = (
        get("CA_HT") + get("Prod_vendue") + get("Prod_stockee") + get("Prod_immobilisee")
        + get("Prestations") + get("Autres_prod_expl")
    )

    CONSOMMATIONS = get("Achats") + get("Variation_stock")
    MARGE_BRUTE = PRODUITS_EXPLOITATION - CONSOMMATIONS

    VALEUR_AJOUTEE_CORRIGEE = (
        MARGE_BRUTE - get("Charges_externes") - get("Sous_traitance")
        - get("Variation_prov_expl_transf")
    )

    EBE = (
        VALEUR_AJOUTEE_CORRIGEE
        - get("Frais_personnel")
        - get("Impots_taxes")
        - get("Frais_divers")
        + get("Produits_divers")
        + get("Transf_charge_expl")
    )

    CHARGES_EXPLOITATION = (
        get("Dotations_amortissements")
        + get("Dotations_provisions")
        + get("Part_capital_loyers_credit_bail")
        + get("Loyers_actifs_expl")
        + get("Solde_operations_communes")
    )

    ENE = EBE + get("Autres_prod_expl_2") - CHARGES_EXPLOITATION

    SOLDE_FINANCIER = get("Produits_financiers") + get("Solde_change_autres") - get("Frais_financiers")

    RCAI = ENE + SOLDE_FINANCIER

    RNC = (
        RCAI
        + get("Charges_produits_sans_effet")
        + get("Plus_minus_cessions")
        + get("Variation_prov_immo_fin")
        + get("Variation_prov_reglementees")
        + get("Autres_prod_charges_exceptionnels")
        - get("Provisions_exceptionnelles")
        - get("Participation_salaries")
        - get("Impots_benefices")
        + get("RNC_explicite")
    )

    return {
        "PRODUITS_EXPLOITATION": PRODUITS_EXPLOITATION,
        "MARGE_BRUTE": MARGE_BRUTE,
        "VALEUR_AJOUTEE_CORRIGEE": VALEUR_AJOUTEE_CORRIGEE,
        "EBE": EBE,
        "CHARGES_EXPLOITATION": CHARGES_EXPLOITATION,
        "ENE": ENE,
        "SOLDE_FINANCIER": SOLDE_FINANCIER,
        "RCAI": RCAI,
        "RNC": RNC,
        "normalized_values": norm_values
    }

# ====================== RATIOS ======================
def compute_tcr_ratios(aggs):
    ca = aggs["PRODUITS_EXPLOITATION"]
    va = aggs["VALEUR_AJOUTEE_CORRIGEE"]
    ebe = aggs["EBE"]
    ene = aggs["ENE"]
    rcai = aggs["RCAI"]
    rnc = aggs["RNC"]

    pct = lambda x, base: (x / base) if base not in (0, None) else None

    return {
        "Marge_brute_sur_CA": pct(aggs["MARGE_BRUTE"], ca),
        "VA_sur_CA": pct(va, ca),
        "EBE_sur_CA": pct(ebe, ca),
        "ENE_sur_CA": pct(ene, ca),
        "RCAI_sur_CA": pct(rcai, ca),
        "RNC_sur_CA": pct(rnc, ca),
        "EBE_sur_VA": pct(ebe, va),
    }

###############################################################################
#                          INTERFACE STREAMLIT                                #
###############################################################################

st.set_page_config(page_title="GibuPet — TCR Auto", layout="wide")
st.title("📊 GibuPet — Plateforme automatique TCR (Saisie manuelle)")

mapping_text = st.sidebar.text_area(
    "Mapping JSON (modifiable)",
    json.dumps(DEFAULT_MAPPING, ensure_ascii=False, indent=2),
    height=350
)

try:
    mapping = json.loads(mapping_text)
except:
    st.sidebar.error("⚠️ Mapping JSON invalide — j'utilise le mapping par défaut.")
    mapping = DEFAULT_MAPPING

st.subheader("Saisir les valeurs manuellement")
postes_map = df_to_poste_value_map_manual(mapping)

if st.button("⚡ Calculer automatiquement"):
    aggs = compute_tcr_aggregates(postes_map, mapping)
    ratios = compute_tcr_ratios(aggs)

    st.subheader("📌 Agrégats calculés")
    df_aggs = pd.DataFrame({k: [v] for k, v in aggs.items() if k != "normalized_values"})
    st.dataframe(df_aggs.T)

    st.subheader("📈 Ratios")
    df_ratios = pd.DataFrame(ratios, index=["Ratio"])
    st.dataframe(df_ratios.T)

    report = {
        "aggregates": aggs,
        "ratios": ratios,
        "postes_map": postes_map
    }
    buf = BytesIO()
    buf.write(json.dumps(report, ensure_ascii=False, indent=2).encode())
    buf.seek(0)

    st.download_button("📥 Télécharger rapport JSON", data=buf, file_name="gibupet_tcr_report.json")
