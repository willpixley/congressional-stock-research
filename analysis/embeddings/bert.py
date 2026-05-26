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
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
from sklearn.preprocessing import normalize
import random
import seaborn as sns
import pandas as pd
import plotly.graph_objects as go
from scipy.cluster import hierarchy
from scipy.spatial.distance import pdist


def get_device() -> str:
    if torch.backends.mps.is_available():
        print("Using MPS (Apple Silicon)")
        return "mps"
    elif torch.cuda.is_available():
        print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
        return "cuda"
    print("Using CPU")
    return "cpu"


_model: SentenceTransformer | None = None


def load_model(model_name: str = "all-mpnet-base-v2") -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name, device=get_device())
        print(f"Loaded model '{model_name}'")
    return _model


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


def agglomerative_clustering(embeddings):

    # dist = pdist(embeddings, metric="cosine")
    # Z = linkage(embeddings, method="average")
    labels = list(embeddings.keys())
    matrix = np.array(list(embeddings.values()))
    embeddings_norm = normalize(matrix)
    Z = linkage(embeddings_norm, method="ward")
    # Create a dendrogram to visualize the hierarchical clustering
    plt.figure(figsize=(10, 8))
    plt.tight_layout(rect=[0, 0.3, 1, 1])  # more bottom space for labels
    plt.subplots_adjust(bottom=0.4)

    dendrogram(Z, labels=labels)
    ax = plt.gca()
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right")
    plt.title("Dendrogram for Agglomerative Clustering")
    plt.xlabel("Companies")
    plt.ylabel("Distance")
    plt.show()


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
    if method == "tsne":
        reducer = TSNE(
            n_components=2, perplexity=min(tsne_perplexity, n - 1), random_state=42
        )
    else:
        reducer = PCA(n_components=2)
    # reducer = UMAP(n_components=2, random_state=42, metric="cosine")

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


def plot_similarity_clustermap(
    committee_embs: dict,
    company_embs: dict,
    sd_threshold: float = 1.0,
    metric: str = "euclidean",
    method: str = "average",
    cmap: str = "mako",
    figsize: tuple = (14, 10),
    save_path: str | None = None,
):
    committees = list(committee_embs.keys())
    companies = list(company_embs.keys())

    comm_mat = np.vstack([committee_embs[c] for c in committees])
    comp_mat = np.vstack([company_embs[c] for c in companies])

    sim = cosine_similarity(comm_mat, comp_mat)
    df = pd.DataFrame(sim, index=committees, columns=companies)

    mu, sigma = sim.mean(), sim.std()
    cutoff = mu + sd_threshold * sigma

    # Linkage on the full (unmasked) data
    row_linkage = hierarchy.linkage(pdist(df.values, metric=metric), method=method)
    col_linkage = hierarchy.linkage(pdist(df.values.T, metric=metric), method=method)

    # Mask below-threshold cells for display only
    masked = np.ma.masked_less(df.values, cutoff)
    display_df = pd.DataFrame(masked, index=df.index, columns=df.columns)

    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(color="white")

    g = sns.clustermap(
        display_df,
        row_linkage=row_linkage,
        col_linkage=col_linkage,
        cmap=cmap_obj,
        vmin=cutoff,
        vmax=float(sim.max()),
        figsize=figsize,
        xticklabels=True,
        yticklabels=True,
        cbar_kws={"label": f"cosine similarity (>= mean + {sd_threshold} SD)"},
        dendrogram_ratio=(0.12, 0.18),
    )
    g.ax_heatmap.set_xticklabels(
        g.ax_heatmap.get_xticklabels(), rotation=90, fontsize=7
    )
    g.ax_heatmap.set_yticklabels(g.ax_heatmap.get_yticklabels(), rotation=0, fontsize=8)
    g.figure.suptitle(
        f"Committee x Company similarity (cutoff={cutoff:.3f}, μ={mu:.3f}, σ={sigma:.3f})",
        y=1.02,
    )

    if save_path:
        g.savefig(save_path, dpi=200, bbox_inches="tight")
    plt.show()
    return g


def plot_similarity_clustermap_plotly(
    committee_embs: dict,
    company_embs: dict,
    sd_threshold: float = 1.0,
    metric: str = "euclidean",
    method: str = "average",
    colorscale: str = "Viridis",
    save_path: str | None = None,
):
    """
    Interactive clustered heatmap of cosine similarities between committees (rows)
    and companies (cols). Cells below mean + sd_threshold * std are rendered
    transparent. Supports hover and zoom.
    """

    committees = list(committee_embs.keys())

    companies = list(company_embs.keys())

    comm_mat = np.vstack([committee_embs[c] for c in committees])
    comp_mat = np.vstack([company_embs[c] for c in companies])

    sim = cosine_similarity(comm_mat, comp_mat)
    df = pd.DataFrame(sim, index=committees, columns=companies)

    mu, sigma = sim.mean(), sim.std()
    cutoff = mu + sd_threshold * sigma

    # Hierarchical clustering -> leaf orderings
    row_linkage = hierarchy.linkage(pdist(df.values, metric=metric), method=method)
    col_linkage = hierarchy.linkage(pdist(df.values.T, metric=metric), method=method)
    row_order = hierarchy.leaves_list(row_linkage)
    col_order = hierarchy.leaves_list(col_linkage)

    df_ord = df.iloc[row_order, col_order]

    # Mask below-threshold cells (NaN -> transparent in Plotly heatmap)
    z = df_ord.values.copy()
    z_display = np.where(z >= cutoff, z, np.nan)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_display,
            x=df_ord.columns.tolist(),
            y=df_ord.index.tolist(),
            colorscale=colorscale,
            zmin=cutoff,
            zmax=float(sim.max()),
            hovertemplate=(
                "Committee: %{y}<br>"
                "Company: %{x}<br>"
                "Cosine sim: %{z:.4f}<extra></extra>"
            ),
            colorbar=dict(title=f"cosine sim<br>(≥ μ + {sd_threshold}σ)"),
        )
    )

    fig.update_layout(
        title=(
            f"Committee × Company similarity "
            f"(cutoff={cutoff:.3f}, μ={mu:.3f}, σ={sigma:.3f})"
        ),
        xaxis=dict(tickangle=-90, tickfont=dict(size=8), showgrid=False),
        yaxis=dict(tickfont=dict(size=9), autorange="reversed", showgrid=False),
        width=1400,
        height=900,
        plot_bgcolor="white",
    )

    if save_path:
        if save_path.endswith(".html"):
            fig.write_html(save_path)
        else:
            fig.write_image(save_path, scale=2)  # needs kaleido

    fig.show()
    return fig


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    committees = {
        "House Foreign Affairs": """# House Committee on Foreign Affairs: Scope and Jurisdiction

## Overview
The House Committee on Foreign Affairs is one of the most significant standing committees in the U.S. House of Representatives, responsible for overseeing all aspects of American foreign policy and international relations. As the primary legislative body for foreign affairs, it holds considerable influence over the nation's diplomatic approach and international engagement.

## Primary Jurisdiction Areas

### Diplomatic Relations and Treaties
The committee reviews and approves all treaties, agreements, and diplomatic protocols that the United States enters into with foreign nations. This includes trade agreements, defense pacts, cultural exchange programs, and multilateral commitments. The committee ensures that these arrangements align with national interests and constitutional requirements.

### International Economic Policy
The committee oversees U.S. economic relations with foreign countries, including trade policies, investment agreements, and economic sanctions. It examines how international economic relationships impact American businesses, workers, and overall economic stability.

### Defense and Security Matters
While the House Armed Services Committee has primary jurisdiction over military appropriations, the Foreign Affairs Committee handles defense-related policies, including foreign military sales, security cooperation programs, and international defense partnerships. This includes oversight of military assistance programs to allied nations.

### International Development and Aid
The committee manages U.S. international development assistance, including foreign aid programs, humanitarian relief efforts, and support for democratic institutions in developing nations. This encompasses both economic development initiatives and programs promoting human rights and democracy abroad.

## Key Responsibilities

### Congressional Oversight
The committee conducts hearings, investigations, and reviews of foreign policy implementation by executive branch agencies. It monitors the effectiveness of diplomatic efforts and ensures proper congressional input in foreign policy decisions.

### Budget and Appropriations
While not directly responsible for the full budget process, the committee reviews and recommends funding levels for foreign affairs programs, international organizations, and diplomatic missions. It works closely with the Appropriations Committee on budgetary matters.

### Legislation Development
The committee drafts, reviews, and recommends legislation related to foreign policy, international trade, diplomatic relations, and global security issues. This includes both standalone bills and amendments to existing laws.

### International Organizations
The committee oversees U.S. participation in international organizations such as the United Nations, World Bank, and International Monetary Fund. It ensures that U.S. contributions and positions align with national interests.

## Areas of Specialized Focus

### Human Rights and Democracy
The committee addresses human rights issues in foreign countries, supports democratic transitions, and monitors the treatment of minorities and political dissidents. This includes oversight of programs promoting democratic governance.

### Global Health and Development
Through various subcommittees, the committee handles global health initiatives, including disease prevention programs, vaccine distribution, and support for healthcare systems in developing nations.

### Energy and Environmental Policy
The committee examines international energy cooperation, climate change initiatives, and environmental protection efforts that require cross-border coordination.

### Counterterrorism and Cybersecurity
The committee addresses international cooperation on counterterrorism efforts, cybersecurity threats, and the prosecution of international criminal activities.

## Subcommittees and Specialized Focus Areas

### Subcommittee on International Organizations
Focuses on U.S. engagement with international bodies and multilateral institutions.

### Subcommittee on Economic Policy
Handles trade, investment, and economic development programs.

### Subcommittee on Human Rights and Democracy
Manages oversight of human rights initiatives and democratic support programs.

## Impact on Policy Making

The committee's influence extends beyond its direct jurisdiction through its role in shaping public policy and providing expert testimony to the full House. Its recommendations significantly impact:
- International trade agreements
- Diplomatic relations with key allies and adversaries
- Military assistance programs
- Foreign aid allocation
- Global humanitarian initiatives

## Challenges and Considerations

### Balancing National Interests
The committee must balance competing national interests, including economic considerations, security concerns, and humanitarian obligations when making policy recommendations.

### Congressional Coordination
Effective foreign policy requires coordination with other committees, particularly the Senate Foreign Relations Committee, and with the executive branch to ensure policy consistency.

### Resource Constraints
The committee's ability to conduct thorough oversight and research is limited by staff resources, budget constraints, and the complexity of international issues.

## Conclusion

The House Committee on Foreign Affairs serves as a critical bridge between American foreign policy objectives and legislative implementation. Its comprehensive jurisdiction over diplomatic relations, international economic policy, and global security issues makes it essential to the functioning of U.S. foreign policy. The committee's work directly impacts how America engages with the world and addresses global challenges, making it one of the most consequential committees in Congress.""",
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

    with open("../data/top_5000_descriptions.json", "r", encoding="utf-8") as f:
        companies = json.load(f)
    with open("../data/hearing.txt", "r", encoding="utf-8") as f:
        committees["Foreign Affairs"] = f.read()

    # MODEL = "ProsusAI/finbert"
    MODEL = "LaBSE"
    # MODEL = "syang687/FinSentenceBERT"
    # MODEL = "all-mpnet-base-v2"
    print("Embedding committees...")
    committee_embs = embed_dict(committees, model_name=MODEL)
    # agglomerative_clustering(committee_embs)

    print("Embedding companies...")
    company_embs = embed_dict(companies, model_name=MODEL)
    # agglomerative_clustering(company_embs)

    combined_embs = company_embs | committee_embs
    # agglomerative_clustering(combined_embs)
    # Ranked similarity for a specific committee
    # target = "House Intelligence Committee"
    # print(f"\nCompanies ranked by similarity to '{target}':")
    # for name, score in rank_similarities(committee_embs[target], company_embs):
    #     print(f"  {name:<25} {score:.4f}")

    # plot_similarity_heatmap(committee_embs, company_embs)

    # plot_clusters(committee_embs, company_embs)
    # plot_similarity_clustermap(committee_embs, company_embs)
    plot_similarity_clustermap_plotly(committee_embs, company_embs, sd_threshold=2)

# hierarchical
# measures of variance and variance lsos in dimensionality reduction
