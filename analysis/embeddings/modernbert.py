import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
import torch
from sentence_transformers import SentenceTransformer
import json
from hdbscan import HDBSCAN
from umap import UMAP


def find_clusters(embeddings: np.ndarray, min_cluster_size: int = 3) -> np.ndarray:
    """
    Returns an array of cluster labels (-1 means noise/outlier).
    """
    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, metric="euclidean")
    return clusterer.fit_predict(embeddings)


# ---------------------------------------------------------------------------
# Device detection
# ---------------------------------------------------------------------------


def get_device() -> str:
    if torch.backends.mps.is_available():
        print("Using MPS (Apple Silicon)")
        return "mps"
    elif torch.cuda.is_available():
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
        return "cuda"
    print("Using CPU")
    return "cpu"


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None


def load_model(model_name: str = "all-mpnet-base-v2") -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name, device=get_device())
        print(f"Loaded model '{model_name}'")
    return _model


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def chunk_text(text: str, max_words: int = 100, overlap: int = 10) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += max_words - overlap
    return chunks


# ---------------------------------------------------------------------------
# 1. Embedding
# ---------------------------------------------------------------------------


def embed(
    text: str,
    max_words: int = 100,
    overlap: int = 10,
    model_name: str = "all-mpnet-base-v2",
) -> np.ndarray:
    model = load_model(model_name)
    chunks = chunk_text(text, max_words=max_words, overlap=overlap)
    if len(chunks) == 1:
        return model.encode(chunks[0], convert_to_numpy=True)
    chunk_embeddings = model.encode(chunks, convert_to_numpy=True)
    weights = np.array([len(c.split()) for c in chunks], dtype=float)
    weights /= weights.sum()
    pooled = np.average(chunk_embeddings, axis=0, weights=weights)
    pooled /= np.linalg.norm(pooled)
    return pooled


def embed_many(
    texts: list[str],
    max_words: int = 100,
    overlap: int = 10,
    model_name: str = "all-mpnet-base-v2",
) -> np.ndarray:
    return np.array(
        [
            embed(t, max_words=max_words, overlap=overlap, model_name=model_name)
            for t in texts
        ]
    )


def embed_dict(
    d: dict[str, str],
    max_words: int = 50,
    overlap: int = 10,
    model_name: str = "all-mpnet-base-v2",
) -> dict[str, np.ndarray]:
    """Embed a name->text dict, returning a name->embedding dict."""
    return {
        name: embed(text, max_words=max_words, overlap=overlap, model_name=model_name)
        for name, text in d.items()
    }


# ---------------------------------------------------------------------------
# 2. Similarity
# ---------------------------------------------------------------------------


def similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
    return float(cosine_similarity(emb_a.reshape(1, -1), emb_b.reshape(1, -1))[0][0])


def similarity_matrix(embeddings: np.ndarray) -> np.ndarray:
    return cosine_similarity(embeddings)


def rank_similarities(
    query_emb: np.ndarray,
    candidate_embs: dict[str, np.ndarray],
) -> list[tuple[str, float]]:
    """Rank candidates by similarity to a query embedding, highest first."""
    scores = {name: similarity(query_emb, emb) for name, emb in candidate_embs.items()}
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# 3. Visualisation
# ---------------------------------------------------------------------------


def plot_similarity_heatmap(
    committee_embs: dict[str, np.ndarray],
    company_embs: dict[str, np.ndarray],
    title: str = "Committee–Company Cosine Similarity",
    figsize: tuple = (14, 8),
) -> None:
    """
    Rectangular heatmap: committees on Y axis, companies on X axis.
    More useful than a square pairwise matrix for your use case.
    """
    committee_names = list(committee_embs.keys())
    company_names = list(company_embs.keys())

    matrix = np.array(
        [
            [similarity(committee_embs[c], company_embs[co]) for co in company_names]
            for c in committee_names
        ]
    )

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    plt.colorbar(im, ax=ax, label="Cosine Similarity")

    ax.set_xticks(range(len(company_names)))
    ax.set_yticks(range(len(committee_names)))
    ax.set_xticklabels(company_names, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(committee_names, fontsize=9)

    for i in range(len(committee_names)):
        for j in range(len(company_names)):
            ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=8)

    ax.set_title(title)
    ax.set_xlabel("Companies")
    ax.set_ylabel("Committees")
    plt.tight_layout()
    plt.show()


def plot_clusters(
    committee_embs: dict[str, np.ndarray],
    company_embs: dict[str, np.ndarray],
    method: str = "tsne",
    title: str = "Embedding Clusters",
    figsize: tuple = (12, 8),
    tsne_perplexity: int = 5,
    min_cluster_size: int = 3,
) -> None:
    names = list(committee_embs.keys()) + list(company_embs.keys())
    embs = np.array(list(committee_embs.values()) + list(company_embs.values()))

    # 1. Reduce dimensions for visualization
    n = len(embs)
    # if method == "tsne":
    #     reducer = TSNE(
    #         n_components=2, perplexity=min(tsne_perplexity, n - 1), random_state=42
    #     )
    # else:
    #     reducer = PCA(n_components=2)
    reducer = UMAP(n_components=2, random_state=42, metric="cosine")

    coords = reducer.fit_transform(embs)

    # 2. Find clusters based on the REDUCED coordinates (usually better for HDBSCAN)
    # Alternatively, run on 'embs' directly if you want clusters in high-dim space
    cluster_labels = find_clusters(coords, min_cluster_size=min_cluster_size)
    print(f"Cluster assignments: {dict(zip(names, cluster_labels))}")

    # 3. Create a color map for clusters
    unique_labels = set(cluster_labels)
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_labels)))
    color_map = {label: colors[i] for i, label in enumerate(sorted(unique_labels))}

    fig, ax = plt.subplots(figsize=figsize)

    # 4. Plot points colored by cluster
    for i, (name, coord) in enumerate(zip(names, coords)):
        label = cluster_labels[i]
        color = color_map[label]

        # Distinguish shape by type (committee vs company)
        marker = (
            "o"
            if "committee" in name.lower()
            or any(k in name for k in ["House", "Senate"])
            else "s"
        )

        ax.scatter(
            coord[0],
            coord[1],
            c=[color],
            marker=marker,
            s=100,
            alpha=0.85,
            edgecolors="black",
            linewidth=0.5,
        )

        # Annotate
        ax.annotate(
            name,
            (coord[0], coord[1]),
            fontsize=7,
            xytext=(6, 4),
            textcoords="offset points",
        )

    # Optional: Add legend for clusters
    # (Legend logic is tricky with dynamic colors, usually better to just show the plot)

    ax.set_title(f"{title} ({method.upper()}, HDBSCAN min_size={min_cluster_size})")
    ax.set_xlabel("Component 1")
    ax.set_ylabel("Component 2")
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    committees = {
        "House Foreign Affairs": """The Full Committee will be responsible for oversight and legislation relating to:

foreign assistance (including development assistance, Millennium Challenge Corporation, the Millennium Challenge Account, HIV/AIDS in foreign countries, security assistance, and Public Law 480 programs abroad);
the Peace Corps;
national security developments affecting foreign policy;
strategic planning and agreements;
war powers, treaties, executive agreements, and the deployment and use of United States Armed Forces;
peacekeeping, peace enforcement, and enforcement of United Nations or other international sanctions;
arms control and disarmament issues;
the United States Agency for International Development;
activities and policies of the State, Commerce and Defense Departments and other agencies related to the Arms Export Control Act, and the Foreign Assistance Act including export and licensing policy for munitions items and technology and dual-use equipment and technology;
international law;
promotion of democracy;
international law enforcement issues, including narcotics control programs and activities;
Broadcasting Board of Governors;
embassy security;
international broadcasting;
public diplomacy, including international communication, information policy, international education, and cultural programs;
and all other matters not specifically assigned to a subcommittee.
The Committee will have jurisdiction over legislation with respect to the administration of the Export Administration Act, including the export and licensing of dual-use equipment and technology and other matters related to international economic policy and trade not otherwise assigned to a subcommittee and with respect to the United Nations, its affiliated agencies and other international organizations, including assessed and voluntary contributions to such organizations. The Committee may conduct oversight with respect to any matter within the jurisdiction of the Committee as defined in the Rules of the House of Representatives.""",
        "House Intelligence Committee": "The United States House Permanent Select Committee on Intelligence (HPSCI) is a committee of the United States House of Representatives. Created in 1977, HPSCI is charged with oversight of the United States Intelligence Community—which includes the intelligence and intelligence-related activities of the following eighteen elements of the U.S. Government—and the Military Intelligence Program.",
        "House Financial Services Committee": """1) Banks and banking, including deposit insurance and Federal monetary policy.

(2) Economic stabilization, defense production, renegotiation, and control of the price of commodities, rents, and services.

(3) Financial aid to commerce and industry (other than transportation).

(4) Insurance generally.

(5) International finance.

(6) International financial and monetary organizations.

(7) Money and credit, including currency and the issuance of notes and redemption thereof; gold and silver, including the coinage thereof; valuation and revaluation of the dollar.

(8) Public and private housing.

(9) Securities and exchanges.

(10) Urban development.""",
        "House Banking, housing, and urban affairs": """. The following standing committees shall be appointed at the commencement of each Congress and shall continue and have the power to act until their successors are appointed, with leave to report by bill or otherwise on matters within their jurisdictions:

(d)(1) Committee on Banking, Housing and Urban Affairs, to which committee shall be referred all proposed legislation, messages, petitions, memorials and other matters relating to the following subjects:

Banks, banking, and financial institutions.
Control of prices of commodities, rents and services.
Deposit insurance.
Economic stabilization and defense production.
Export and foreign trade promotion.
Export controls.
Federal monetary policy, including the Federal Reserve System.
Financial aid to commerce and industry.
Issuance and redemption of notes.
Money and credit, including currency and coinage.
Nursing home construction.
Public and private housing (including veterans housing).
Renegotiation of Government contracts.
Urban development and urban mass transit.
(2) Such Committee shall also study and review on a comprehensive basis, matters relating to international economic policy as it affects United States monetary affairs, credit, and financial institutions; economic growth, urban affairs, and credit, and report thereon from time to time.""",
        "Gibberish": """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Tellus risus bibendum vestibulum arcu aliquam orci et primis sagittis habitant scelerisque ridiculus donec accumsan. Leo nullam cum taciti netus curabitur etiam molestie tellus neque justo quam hac duis penatibus. Est vivamus litora nam elit odio erat taciti molestie sociis auctor nunc auctor at quisque. Ridiculus sapien scelerisque pretium venenatis himenaeos fermentum sed sagittis at sollicitudin elementum nunc natoque potenti. Convallis cubilia dui senectus potenti vehicula hendrerit lacinia mus quam imperdiet nunc turpis cras primis. Aliquam fermentum class leo dapibus nisi tortor ante urna consequat convallis etiam nam inceptos dolor. Eget rhoncus risus conubia molestie dapibus feugiat habitasse sodales lorem nunc blandit vivamus ultricies taciti. Sem sagittis mollis mauris aliquet mollis litora aliquam dictum sapien eros nascetur lacus vestibulum est. Tortor hendrerit consequat imperdiet curae pulvinar faucibus fermentum tellus cum sed hendrerit velit dolor convallis.""",
        "House Foreign Policy Oversight Committee (Test)": """This committee handles oversight of U.S. international relations, including diplomatic missions, foreign aid programs, and international treaty negotiations. It reviews budget allocations for State Department activities and monitors implementation of foreign policy directives. The committee also examines issues related to international security cooperation, multilateral agreements with allied nations, and U.S. participation in global diplomatic initiatives. It oversees the operations of international development programs and ensures alignment with national security objectives.""",
        "House Ethics Committee": """House Rule 10, clause 1(g)

The Committee on Ethics has jurisdiction over all bills, resolutions and other matters relating to the Code of Official Conduct adopted under House Rule 23.

You can read the Code of Official Conduct here.

House Rule 11, clause 3

With respect to Members, officers, and employees of the U.S. House of Representatives, the Committee on Ethics is authorized to undertake the following actions:

A) Recommend administrative actions to establish or enforce standards of official conduct.

B) Investigate alleged violations of the Code of Official Conduct or of any applicable rules, laws, or regulations governing the performance of official duties or the discharge of official responsibilities. Such investigations must be made in accordance with Committee rules.

C) Report to appropriate federal or state authorities substantial evidence of a violation of any law applicable to the performance of official duties that may have been disclosed in a Committee investigation. Such reports must be approved by the House or by an affirmative vote of two-thirds of the Committee.

D) Render advisory opinions regarding the propriety of any current or proposed conduct of a Member, officer, or employee, and issue general guidance on such matters as necessary.

E) Consider requests for written waivers of the gift rule (clause 5 of House Rule 25)

House Rule 25, clause 5(h)

All provisions of the gift rule are to be interpreted and enforced solely by the Committee on Ethics. The Committee is authorized to issue guidance on any matter contained in the rule.

Ethics in Government Act (5 U.S.C. § 13101 et seq.; adopted as House Rule 26)

The Ethics in Government Act (EIGA) designates the Committee on Ethics as the “supervising ethics office” for the House of Representatives and charges the Committee with duties and responsibilities for Financial Disclosure Statements (Title I) and for Outside Employment (Title V) with respect to Members, officers, and employees of the House of Representatives.

The statute also charges the Committee with duties and responsibilities with regard to (1) the Financial Disclosure Statements of candidates for the House, and (2) the Financial Disclosure Statements and outside employment of officers and employees of certain legislative branch agencies, including the Library of Congress, Congressional Budget Office, Government Printing Office, Architect of the Capitol, United States Capitol Police, and United States Botanic Garden. However, the Committee has delegated much of its authority with regard to the officers and employees of those entities to the heads of those entities.

Foreign Gifts and Decorations Act (5 U.S.C. § 7342)

The Foreign Gifts and Decorations Act (FGDA) designates the Committee on Ethics as the “employing agency” for the House of Representatives and charges the Committee with administering the provisions of the FGDA with respect to Members, officers, and employees of the House of Representatives.

Gifts to Superiors (5 U.S.C. § 7351)

The Committee on Ethics is designated the “supervising ethics office” for the House of Representatives for 5 U.S.C. § 7351 which prohibits Members, officers, and employees of the House of Representatives from giving gifts to an official superior or receiving gifts from employees with a lower salary level.

Committee authority with regard to the employees of certain legislative branch entities has been delegated to the heads of those entities (see the section on the Ethics in Government Act above).

Gifts to Federal Employees (5 U.S.C. § 7353)

The Committee on Ethics is designated the “supervising ethics office” for the House of Representatives for 5 U.S.C. § 7353 which prohibits Members, officers, and employees of the House of Representatives from soliciting or receiving gifts.

Committee authority with regard to the employees of certain legislative branch entities has been delegated to the heads of those entities (see the section on the Ethics in Government Act above).""",
    }

    # companies = {
    #     "ExxonMobil": """Exxon Mobil Corporation engages in the exploration and production of crude oil and natural gas in the United States, Canada, and internationally. The company operates through Upstream, Energy Products, Chemical Products, and Specialty Products segments. Its Upstream segment explores for and produces crude oil and natural gas. The Energy Products segment offers fuels, aromatics, and catalysts, as well as licensing services. Its Chemical Products segment manufactures and sells olefins, polyolefins, and intermediates. The Specialty Products segment offers finished lubricants, basestocks, waxes, synthetics, elastomers, and resins. It is also involved in the manufacture, trade, transport, and sale of crude oil, natural gas, petroleum products, petrochemicals, and other specialty products; and pursuit of lower-emission and business opportunities, including carbon capture and storage, hydrogen, lower-emission fuels, Proxxima resin systems, carbon materials, low-carbon data center, and lithium. In addition, the company offers aviation fuel. It sells its products under the Exxon, Esso, and Mobil brands. Exxon Mobil Corporation was founded in 1870 and is headquartered in Spring, Texas.""",
    #     "Lockheed Martin": """Lockheed Martin Corporation, an aerospace and defense company, engages in the research, design, development, manufacture, integration, and sustainment of technology systems, products, and services in the United States, Europe, Asia, the Middle East, and internationally. The company operates through four segments: Aeronautics; Missiles and Fire Control (MFC); Rotary and Mission Systems (RMS); and Space. The Aeronautics segment offers combat and air mobility aircraft, unmanned air vehicles, and related technologies. The MFC segment provides air and missile defense systems; tactical missiles and precision strike weapon systems; logistics; fire control systems; mission operations support, readiness, engineering support, and integration services; and ground vehicles. The RMS segment offers military and commercial helicopters, surface ships, sea and land-based missile defense systems, radar and laser systems, sea and air-based mission and combat systems, command and control mission solutions, cyber solutions, simulation and training solutions, and services and supports surface ships. The Space segment provides satellites; space transportation systems; strategic, advanced strike, and defensive systems; and classified systems and services in support of national security systems. This segment also provides network-enabled situational awareness and integrates space and ground global systems to help its customers gather, analyze, and securely distribute critical intelligence data. It serves primarily serves the U.S. government and international customers, as well as foreign military sales contracted through the U.S. government. The company was formerly known as The Lockheed Corporation and changed its name to Lockheed Martin Corporation in March 1995. Lockheed Martin Corporation was founded in 1912 and is based in Bethesda, Maryland.""",
    #     "JPMorgan Chase": """JPMorgan Chase & Co. operates as a bank and financial holding company in the United States, rest of North America, Europe, the Middle East, Africa, the Asia Pacific, Latin America, and the Caribbean. It operates in three segments: Consumer & Community Banking, Commercial & Investment Bank, and Asset & Wealth Management. The company offers deposit, investment and lending products, and cash management; mortgage origination and servicing activities; residential mortgages and home equity loans; and credit cards, payment solutions, travel services, merchant offers, lifestyle benefits, auto loans, and leases to consumers and small businesses through bank branches, ATMs, and digital and telephone banking. It also provides investment banking, market-making, financing, custody, and securities products and services; corporate strategy and structure advisory, equity and debt market capital-raising, and loan origination and syndication services; cash and derivative instruments, risk management solutions, prime brokerage, clearing, and research; and fund services, liquidity and trading services, and data solutions products for large corporations, financial institutions, merchants, start-ups, small and midsized companies, local governments, municipalities, nonprofits, and commercial real estate clients. In addition, the company offers multi-asset investment management solutions in equities, fixed income, alternatives, and money market funds to institutional clients and retail investors; retirement products and services, estate planning, lending, deposits, and investment management products to high-net-worth clients; and financial transaction processing. JPMorgan Chase & Co. was founded in 1799 and is headquartered in New York, New York.""",
    #     "Citigroup": """Citigroup Inc., a diversified financial service holding company, provides various financial products and services to consumers, corporations, governments, and institutions. It operates through five segments: Services, Markets, Banking, U.S. Personal Banking, and Wealth. The Services segment includes treasury and trade solutions, which provides cash management, trade, and working capital solutions to multinational corporations, financial institutions, and public sector organizations; and securities services, such as cross-border support for clients, local market expertise, post-trade technologies, data solutions, and various securities services solutions. The Markets segment offers sales and trading services for equities, foreign exchange, rates, spread products, and commodities to corporate, institutional, and public sector clients; and market-making services, including asset classes, risk management solutions, financing, and prime brokerage. The Banking segment includes investment banking services comprising equity and debt capital markets-related strategic financing solutions; advisory services related to mergers and acquisitions, divestitures, restructurings, and corporate defense activities; and corporate lending consists of corporate and commercial banking. The U.S. Personal Banking segment provides proprietary and co-branded card portfolios; and traditional banking services to retail and small business customers. The Wealth segment offers financial services to high-net-worth clients through banking, lending, mortgages, investment, custody, and trust product offerings; professional industries, including law firms, consulting groups, accounting, and asset management; and affluent and high net worth clients. The company operates in North America, the United Kingdom, Japan, North and South Asia, Australia, Europe, the Middle East, and Africa. Citigroup Inc. was founded in 1812 and is headquartered in New York, New York.""",
    #     "Global Diplomatic Solutions Inc. (Test)": "This company specializes in international policy consulting and diplomatic relations management. It provides advisory services for foreign affairs initiatives, manages international development funding programs, and supports diplomatic mission operations. The firm assists with treaty negotiation preparation and international security cooperation frameworks. It offers expertise in multilateral agreement implementation, allied nation relationship management, and global diplomatic initiative coordination. The company also handles international development program oversight and ensures foreign policy directive compliance.",
    # }
    with open("../data/company_descriptions.json", "r", encoding="utf-8") as f:
        companies = json.load(f)

    import random

    # Assuming 'original_dict' is your large dictionary
    original_dict = companies  # From your previous step

    # Randomly sample 100 items (returns a list of tuples: (key, value))
    sampled_items = list(original_dict.items())[:30]

    # Convert back to a dictionary
    companies = dict(sampled_items)

    MODEL = "nomic-ai/modernbert-embed-base"

    print("Embedding committees...")
    committee_embs = embed_dict(committees, model_name=MODEL)

    print("Embedding companies...")
    company_embs = embed_dict(companies, model_name=MODEL)

    # Ranked similarity for a specific committee
    target = "House Intelligence Committee"
    print(f"\nCompanies ranked by similarity to '{target}':")
    for name, score in rank_similarities(committee_embs[target], company_embs):
        print(f"  {name:<25} {score:.4f}")

    # Heatmap — committees vs companies
    plot_similarity_heatmap(committee_embs, company_embs)

    # Cluster plot
    plot_clusters(committee_embs, company_embs)
