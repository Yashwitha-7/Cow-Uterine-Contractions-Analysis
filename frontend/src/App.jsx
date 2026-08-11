import { useState } from "react";
import {
  DatabaseOutlined,
  BarChartOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  HomeOutlined,
  LineChartOutlined,
  UploadOutlined,
  WarningOutlined,
  SwapOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";

import VisualAnalysisPage from "./pages/VisualAnalysisPage";
import UploadPage from "./pages/UploadPage";
import CowListPage from "./pages/CowListPage";
import UploadHistoryPage from "./pages/UploadHistoryPage";
import QCLogsPage from "./pages/QCLogsPage";
import DataPreviewPage from "./pages/DataPreviewPage";
import Phase3ProcessingPage from "./pages/Phase3ProcessingPage";
import ClockLabExportPage from "./pages/ClockLabExportPage";
import DownloadsPage from "./pages/DownloadsPage";
import PolarityReviewPage from "./pages/PolarityReviewPage";
import "./index.css";

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const MENU_ITEMS = [
  {
    key: "polarity",
    icon: <SwapOutlined />,
    label: "Polarity Review",
  },
  {
    key: "visual",
    icon: <BarChartOutlined />,
    label: "Visual Analysis",
  },
  {
    key: "upload",
    icon: <UploadOutlined />,
    label: "Upload Data",
  },
  {
    key: "cows",
    icon: <HomeOutlined />,
    label: "Cow List",
  },
  {
    key: "history",
    icon: <HistoryOutlined />,
    label: "Upload History",
  },
  {
    key: "qc",
    icon: <WarningOutlined />,
    label: "QC Logs",
  },
  {
    key: "preview",
    icon: <FileSearchOutlined />,
    label: "Data Preview",
  },
  {
    key: "phase3",
    icon: <ExperimentOutlined />,
    label: "Phase 3 Processing",
  },
  {
    key: "clocklab",
    icon: <LineChartOutlined />,
    label: "ClockLab Export",
  },
  {
    key: "downloads",
    icon: <DownloadOutlined />,
    label: "Downloads",
  },
];

function renderPage(selectedKey) {
  switch (selectedKey) {
    case "upload":
      return <UploadPage />;
    case "visual":
      return <VisualAnalysisPage />;
    case "cows":
      return <CowListPage />;
    case "history":
      return <UploadHistoryPage />;
    case "qc":
      return <QCLogsPage />;
    case "preview":
      return <DataPreviewPage />;
    case "phase3":
      return <Phase3ProcessingPage />;
    case "polarity":
      return <PolarityReviewPage />;
    case "clocklab":
      return <ClockLabExportPage />;
    case "downloads":
      return <DownloadsPage />;
    default:
      return <UploadPage />;
  }
}

export default function App() {
  const [selectedKey, setSelectedKey] = useState("upload");

  return (
    <Layout className="app-shell">
      <Sider width={250} theme="light" className="cow-sidebar">
        <div className="brand-block">
          <div className="lab-mark" aria-hidden="true">HL</div>
          <div>
          <Title level={4} style={{ margin: 0 }}>
            Cow Contractions
          </Title>
          <Text type="secondary">Hoffmann Lab monitoring</Text>
          </div>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={(item) => setSelectedKey(item.key)}
          className="cow-menu"
        />
      </Sider>

      <Layout>
        <Header className="app-header">
          <DatabaseOutlined style={{ fontSize: 22, marginRight: 12 }} />
          <Title level={4} style={{ margin: 0 }}>
            Research Analysis Dashboard
          </Title>
        </Header>

        <Content className="app-content">
          {renderPage(selectedKey)}
        </Content>
      </Layout>
    </Layout>
  );
}
