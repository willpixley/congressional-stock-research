import torch
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModel, AutoTokenizer
import matplotlib.pyplot as plt
import numpy as np

# Device setup
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained("yiyanghkust/finbert-tone", use_fast=False)
model = AutoModel.from_pretrained("yiyanghkust/finbert-tone", use_fast=False)


# Function to get CLS embedding
def get_cls_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True).to(
        device
    )
    with torch.no_grad():
        outputs = model(**inputs)
        cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    return cls_embedding


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
}

companies = {
    "ExxonMobil": """Exxon Mobil Corporation engages in the exploration and production of crude oil and natural gas in the United States, Canada, and internationally. The company operates through Upstream, Energy Products, Chemical Products, and Specialty Products segments. Its Upstream segment explores for and produces crude oil and natural gas. The Energy Products segment offers fuels, aromatics, and catalysts, as well as licensing services. Its Chemical Products segment manufactures and sells olefins, polyolefins, and intermediates. The Specialty Products segment offers finished lubricants, basestocks, waxes, synthetics, elastomers, and resins. It is also involved in the manufacture, trade, transport, and sale of crude oil, natural gas, petroleum products, petrochemicals, and other specialty products; and pursuit of lower-emission and business opportunities, including carbon capture and storage, hydrogen, lower-emission fuels, Proxxima resin systems, carbon materials, low-carbon data center, and lithium. In addition, the company offers aviation fuel. It sells its products under the Exxon, Esso, and Mobil brands. Exxon Mobil Corporation was founded in 1870 and is headquartered in Spring, Texas.""",
    "Lockheed Martin": """Lockheed Martin Corporation, an aerospace and defense company, engages in the research, design, development, manufacture, integration, and sustainment of technology systems, products, and services in the United States, Europe, Asia, the Middle East, and internationally. The company operates through four segments: Aeronautics; Missiles and Fire Control (MFC); Rotary and Mission Systems (RMS); and Space. The Aeronautics segment offers combat and air mobility aircraft, unmanned air vehicles, and related technologies. The MFC segment provides air and missile defense systems; tactical missiles and precision strike weapon systems; logistics; fire control systems; mission operations support, readiness, engineering support, and integration services; and ground vehicles. The RMS segment offers military and commercial helicopters, surface ships, sea and land-based missile defense systems, radar and laser systems, sea and air-based mission and combat systems, command and control mission solutions, cyber solutions, simulation and training solutions, and services and supports surface ships. The Space segment provides satellites; space transportation systems; strategic, advanced strike, and defensive systems; and classified systems and services in support of national security systems. This segment also provides network-enabled situational awareness and integrates space and ground global systems to help its customers gather, analyze, and securely distribute critical intelligence data. It serves primarily serves the U.S. government and international customers, as well as foreign military sales contracted through the U.S. government. The company was formerly known as The Lockheed Corporation and changed its name to Lockheed Martin Corporation in March 1995. Lockheed Martin Corporation was founded in 1912 and is based in Bethesda, Maryland.""",
    "JPMorgan Chase": """JPMorgan Chase & Co. operates as a bank and financial holding company in the United States, rest of North America, Europe, the Middle East, Africa, the Asia Pacific, Latin America, and the Caribbean. It operates in three segments: Consumer & Community Banking, Commercial & Investment Bank, and Asset & Wealth Management. The company offers deposit, investment and lending products, and cash management; mortgage origination and servicing activities; residential mortgages and home equity loans; and credit cards, payment solutions, travel services, merchant offers, lifestyle benefits, auto loans, and leases to consumers and small businesses through bank branches, ATMs, and digital and telephone banking. It also provides investment banking, market-making, financing, custody, and securities products and services; corporate strategy and structure advisory, equity and debt market capital-raising, and loan origination and syndication services; cash and derivative instruments, risk management solutions, prime brokerage, clearing, and research; and fund services, liquidity and trading services, and data solutions products for large corporations, financial institutions, merchants, start-ups, small and midsized companies, local governments, municipalities, nonprofits, and commercial real estate clients. In addition, the company offers multi-asset investment management solutions in equities, fixed income, alternatives, and money market funds to institutional clients and retail investors; retirement products and services, estate planning, lending, deposits, and investment management products to high-net-worth clients; and financial transaction processing. JPMorgan Chase & Co. was founded in 1799 and is headquartered in New York, New York.""",
    "Citigroup": """Citigroup Inc., a diversified financial service holding company, provides various financial products and services to consumers, corporations, governments, and institutions. It operates through five segments: Services, Markets, Banking, U.S. Personal Banking, and Wealth. The Services segment includes treasury and trade solutions, which provides cash management, trade, and working capital solutions to multinational corporations, financial institutions, and public sector organizations; and securities services, such as cross-border support for clients, local market expertise, post-trade technologies, data solutions, and various securities services solutions. The Markets segment offers sales and trading services for equities, foreign exchange, rates, spread products, and commodities to corporate, institutional, and public sector clients; and market-making services, including asset classes, risk management solutions, financing, and prime brokerage. The Banking segment includes investment banking services comprising equity and debt capital markets-related strategic financing solutions; advisory services related to mergers and acquisitions, divestitures, restructurings, and corporate defense activities; and corporate lending consists of corporate and commercial banking. The U.S. Personal Banking segment provides proprietary and co-branded card portfolios; and traditional banking services to retail and small business customers. The Wealth segment offers financial services to high-net-worth clients through banking, lending, mortgages, investment, custody, and trust product offerings; professional industries, including law firms, consulting groups, accounting, and asset management; and affluent and high net worth clients. The company operates in North America, the United Kingdom, Japan, North and South Asia, Australia, Europe, the Middle East, and Africa. Citigroup Inc. was founded in 1812 and is headquartered in New York, New York.""",
    "Global Diplomatic Solutions Inc. (Test)": "This company specializes in international policy consulting and diplomatic relations management. It provides advisory services for foreign affairs initiatives, manages international development funding programs, and supports diplomatic mission operations. The firm assists with treaty negotiation preparation and international security cooperation frameworks. It offers expertise in multilateral agreement implementation, allied nation relationship management, and global diplomatic initiative coordination. The company also handles international development program oversight and ensures foreign policy directive compliance.",
}

# Generate embeddings
committee_embeddings = [get_cls_embedding(desc)[0] for desc in committees.values()]
company_embeddings = [get_cls_embedding(desc)[0] for desc in companies.values()]

# Compute similarity matrix
similarity_matrix = cosine_similarity(committee_embeddings, company_embeddings)

# Plot heatmap
plt.figure(figsize=(8, 6))
plt.imshow(similarity_matrix, cmap="YlGnBu", aspect="auto")
plt.colorbar(label="Cosine Similarity")
plt.xticks(range(len(companies)), list(companies.keys()), rotation=45)
plt.yticks(range(len(committees)), list(committees.keys()))
plt.title("Committee vs Company Similarity")
for i in range(len(committees)):
    for j in range(len(companies)):
        plt.text(j, i, f"{similarity_matrix[i][j]:.2f}", ha="center", va="center")
plt.tight_layout()
plt.show()
