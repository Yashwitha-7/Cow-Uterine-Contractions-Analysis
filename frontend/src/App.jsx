import { useState } from "react";
import { Layout, Menu } from "antd";
import { AppHeader } from "./components/AppHeader";
import { UploadPage } from "./pages/UploadPage";
import { DownloadPage } from "./pages/DownloadPage";

const { Content } = Layout;

function App() {
  const [page, setPage] = useState("upload");

  return (
    <Layout style={{ minHeight: "100vh", background: "#f4f7f2" }}>
      <AppHeader />

      <Menu
        mode="horizontal"
        selectedKeys={[page]}
        onClick={(event) => setPage(event.key)}
        items={[
          { key: "upload", label: "Upload Data" },
          { key: "download", label: "Download CSV" },
        ]}
        style={{
          paddingLeft: 24,
          borderBottom: "1px solid #d7dfd8",
        }}
      />

      <Content style={{ padding: "0 24px 40px" }}>
        {page === "upload" && <UploadPage />}
        {page === "download" && <DownloadPage />}
      </Content>
    </Layout>
  );
}

export default App;