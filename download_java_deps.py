"""
Java Maven 依赖下载器
从 Maven Central 解析 pom.xml 并下载所有传递依赖的 jar 包
"""
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import hashlib

MAVEN_CENTRAL = "https://repo1.maven.org/maven2"
TARGET_DIR = r"D:\AI_projects\zhongzhai_pro\project-proposal-ai\项目依赖\Java依赖"
POM_FILE = r"D:\AI_projects\zhongzhai_pro\project-proposal-ai\proposal-java\pom.xml"

# Spring Boot 3.2.5 starter 预计算依赖 (从 Maven Central BOM 获取)
# 这些是 spring-boot-starter-parent 3.2.5 的精确传递依赖
SPRING_BOOT_VERSION = "3.2.5"

# 下载计数
downloaded = 0
failed = []
resolved = set()  # (groupId, artifactId) 已处理的

def download_file(url, dest):
    """下载文件"""
    global downloaded
    if os.path.exists(dest):
        return True
    try:
        print(f"  下载: {os.path.basename(dest)}", end=" ")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        urllib.request.urlretrieve(url, dest)
        downloaded += 1
        print("✅")
        return True
    except Exception as e:
        print(f"❌ {e}")
        failed.append(url)
        return False

def resolve_pom(groupId, artifactId, version, scope="compile"):
    """解析 POM 并返回传递依赖"""
    if (groupId, artifactId) in resolved:
        return []
    resolved.add((groupId, artifactId))
    
    if scope in ("test", "provided"):
        return []
    
    path = f"{groupId.replace('.', '/')}/{artifactId}/{version}/{artifactId}-{version}.pom"
    url = f"{MAVEN_CENTRAL}/{path}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        
        # 解析 XML（处理命名空间）
        root = ET.fromstring(content)
        ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
        
        # 提取父 POM
        parent = root.find('mvn:parent', ns)
        if parent is not None:
            p_gid = parent.find('mvn:groupId', ns)
            p_aid = parent.find('mvn:artifactId', ns)
            p_ver = parent.find('mvn:version', ns)
            if p_gid is not None and p_aid is not None:
                gid = p_gid.text
                aid = p_aid.text
                ver = p_ver.text if p_ver is not None else version
                resolve_pom(gid, aid, ver)
        
        # 提取依赖管理
        dep_mgmt = root.find('mvn:dependencyManagement', ns)
        managed_versions = {}
        if dep_mgmt is not None:
            deps_elem = dep_mgmt.find('mvn:dependencies', ns)
            if deps_elem is not None:
                for dep in deps_elem.findall('mvn:dependency', ns):
                    mg = dep.find('mvn:groupId', ns)
                    ma = dep.find('mvn:artifactId', ns)
                    mv = dep.find('mvn:version', ns)
                    if mg is not None and ma is not None and mv is not None:
                        managed_versions[(mg.text, ma.text)] = mv.text
        
        # 提取直接依赖
        deps = []
        deps_elem = root.find('mvn:dependencies', ns)
        if deps_elem is not None:
            for dep in deps_elem.findall('mvn:dependency', ns):
                dg = dep.find('mvn:groupId', ns)
                da = dep.find('mvn:artifactId', ns)
                dv = dep.find('mvn:version', ns)
                ds = dep.find('mvn:scope', ns)
                do = dep.find('mvn:optional', ns)
                
                gid = dg.text if dg is not None else None
                aid = da.text if da is not None else None
                ver = dv.text if dv is not None else managed_versions.get((gid, aid), version)
                sco = ds.text if ds is not None else "compile"
                opt = do.text if do is not None else "false"
                
                if gid and aid and ver and opt != "true":
                    deps.append((gid, aid, ver, sco))
        
        return deps
    except Exception as e:
        print(f"  POM解析失败: {groupId}:{artifactId}:{version} - {e}")
        return []

def download_jar(groupId, artifactId, version):
    """下载 jar 包"""
    filename = f"{artifactId}-{version}.jar"
    path = f"{groupId.replace('.', '/')}/{artifactId}/{version}/{filename}"
    url = f"{MAVEN_CENTRAL}/{path}"
    dest = os.path.join(TARGET_DIR, filename)
    return download_file(url, dest)

def process_deps(deps, depth=0):
    """递归处理依赖"""
    prefix = "  " * depth
    for groupId, artifactId, version, scope in deps:
        if scope in ("test", "provided"):
            continue
        
        key = (groupId, artifactId)
        if key in resolved:
            continue
        
        print(f"{prefix}{groupId}:{artifactId}:{version} [{scope}]")
        download_jar(groupId, artifactId, version)
        
        # 递归解析
        transitive = resolve_pom(groupId, artifactId, version, scope)
        if transitive:
            process_deps(transitive, depth + 1)

def main():
    print("=" * 60)
    print("Java 依赖下载器 - 从 Maven Central 下载")
    print("=" * 60)
    print()
    
    # 确保目标目录存在
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    # 解析项目 POM
    print("解析 pom.xml...")
    ns = {'mvn': 'http://maven.apache.org/POM/4.0.0'}
    tree = ET.parse(POM_FILE)
    root = tree.getroot()
    
    # 查找 parent POM 版本
    parent = root.find('mvn:parent', ns)
    sb_version = "3.2.5"
    if parent is not None:
        ver_elem = parent.find('mvn:version', ns)
        if ver_elem is not None:
            sb_version = ver_elem.text
    print(f"Spring Boot 版本: {sb_version}")
    
    # 首先解析 Spring Boot parent POM (获取所有 managed versions)
    print("\n解析 Spring Boot parent POM (获取所有版本号)...")
    resolve_pom("org.springframework.boot", "spring-boot-starter-parent", sb_version)
    resolve_pom("org.springframework.boot", "spring-boot-dependencies", sb_version)
    
    # 解析项目直接依赖
    print("\n解析项目直接依赖...")
    deps = []
    managed_versions = {}
    
    # 提取 managed versions (从已解析的 BOM)
    # Spring Boot 项目的版本由 starter-parent 统一管理
    # 对于非 Spring 的依赖，需要手动指定
    
    deps_elem = root.find('mvn:dependencies', ns)
    if deps_elem is not None:
        for dep in deps_elem.findall('mvn:dependency', ns):
            dg = dep.find('mvn:groupId', ns)
            da = dep.find('mvn:artifactId', ns)
            dv = dep.find('mvn:version', ns)
            ds = dep.find('mvn:scope', ns)
            
            gid = dg.text
            aid = da.text
            ver = dv.text if dv is not None else "3.2.5"
            sco = ds.text if ds is not None else "compile"
            
            deps.append((gid, aid, ver, sco))
    
    print(f"\n共 {len(deps)} 个直接依赖")
    print("\n开始下载...")
    print()
    
    process_deps(deps)
    
    print()
    print("=" * 60)
    print(f"下载完成: {downloaded} 个 jar 文件")
    print(f"目标目录: {TARGET_DIR}")
    if failed:
        print(f"失败: {len(failed)} 个")
        for f in failed:
            print(f"  {f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
