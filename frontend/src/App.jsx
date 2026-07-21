import { useState } from "react";
import {
  DatabaseOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  HomeOutlined,
  LineChartOutlined,
  UploadOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";

import { BarChartOutlined } from "@ant-design/icons";
import VisualAnalysisPage from "./pages/VisualAnalysisPage";
import UploadPage from "./pages/UploadPage";
import CowListPage from "./pages/CowListPage";
import UploadHistoryPage from "./pages/UploadHistoryPage";
import QCLogsPage from "./pages/QCLogsPage";
import DataPreviewPage from "./pages/DataPreviewPage";
import Phase3ProcessingPage from "./pages/Phase3ProcessingPage";
import ClockLabExportPage from "./pages/ClockLabExportPage";
import DownloadsPage from "./pages/DownloadsPage";

const { Header, Sider, Content } = Layout;
const { Title, Text } = Typography;

const MENU_ITEMS = [
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
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={260} theme="light">
        <div style={{ padding: 20, borderBottom: "1px solid #f0f0f0" }}>
          <Title level={4} style={{ margin: 0 }}>
            Hoffmann Lab
          </Title>
          <Text type="secondary">Cow Uterine Contraction Analysis</Text>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={(item) => setSelectedKey(item.key)}
          style={{ borderRight: 0 }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: "#ffffff",
            borderBottom: "1px solid #f0f0f0",
            display: "flex",
            alignItems: "center",
            paddingLeft: 24,
          }}
        >
          <DatabaseOutlined style={{ fontSize: 22, marginRight: 12 }} />
          <Title level={4} style={{ margin: 0 }}>
            Local Data Processing Dashboard
          </Title>
        </Header>

        <Content style={{ padding: 24, background: "#f5f7f6" }}>
          {renderPage(selectedKey)}
        </Content>
      </Layout>
    </Layout>
  );
}