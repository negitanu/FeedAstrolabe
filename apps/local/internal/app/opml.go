package app

import (
	"encoding/xml"
	"errors"
	"strings"
)

type Outline struct {
	Text     string    `xml:"text,attr,omitempty"`
	Title    string    `xml:"title,attr,omitempty"`
	Type     string    `xml:"type,attr,omitempty"`
	URL      string    `xml:"xmlUrl,attr,omitempty"`
	Site     string    `xml:"htmlUrl,attr,omitempty"`
	Children []Outline `xml:"outline"`
}
type OPML struct {
	XMLName  xml.Name  `xml:"opml"`
	Version  string    `xml:"version,attr"`
	Title    string    `xml:"head>title"`
	Outlines []Outline `xml:"body>outline"`
}
type ImportFeed struct {
	URL       string `json:"url"`
	Title     string `json:"title"`
	Folder    string `json:"folder"`
	Duplicate bool   `json:"duplicate"`
	Error     string `json:"error"`
}

func (s *Store) PreviewOPML(raw string) ([]ImportFeed, error) {
	if len(raw) > maxDownload {
		return nil, errors.New("OPMLは5MiBまでです")
	}
	if err := safeXML([]byte(raw)); err != nil {
		return nil, err
	}
	var doc OPML
	if err := xml.Unmarshal([]byte(raw), &doc); err != nil {
		return nil, errors.New("OPMLを解析できません")
	}
	feeds, err := s.Feeds()
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	for _, f := range feeds {
		seen[f.URL] = true
	}
	out := []ImportFeed{}
	var walk func([]Outline, string, int) error
	walk = func(items []Outline, folder string, depth int) error {
		if depth > 32 {
			return errors.New("OPML階層が深すぎます")
		}
		for _, v := range items {
			title := v.Title
			if title == "" {
				title = v.Text
			}
			if v.URL != "" {
				u, e := parseURL(v.URL)
				item := ImportFeed{URL: v.URL, Title: title, Folder: folder}
				if e != nil {
					item.Error = e.Error()
				} else {
					item.URL = u.String()
					item.Duplicate = seen[item.URL]
					seen[item.URL] = true
				}
				if item.Title == "" {
					item.Title = item.URL
				}
				out = append(out, item)
				if len(out) > 500 {
					return errors.New("OPMLは500購読までです")
				}
			}
			next := folder
			if v.URL == "" && title != "" {
				if next != "" {
					next += " / "
				}
				next += title
			}
			if e := walk(v.Children, next, depth+1); e != nil {
				return e
			}
		}
		return nil
	}
	if err = walk(doc.Outlines, "", 0); err != nil {
		return nil, err
	}
	return out, nil
}
func (s *Store) ImportOPML(raw string) (map[string]int, error) {
	items, err := s.PreviewOPML(raw)
	if err != nil {
		return nil, err
	}
	tx, err := s.DB.Begin()
	if err != nil {
		return nil, err
	}
	defer tx.Rollback()
	folderIDs := map[string]int64{}
	rows, err := tx.Query("SELECT id,name FROM folders")
	if err != nil {
		return nil, err
	}
	for rows.Next() {
		var id int64
		var name string
		if err = rows.Scan(&id, &name); err != nil {
			rows.Close()
			return nil, err
		}
		folderIDs[name] = id
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return nil, err
	}
	added, skipped := 0, 0
	for _, v := range items {
		if v.Duplicate || v.Error != "" {
			skipped++
			continue
		}
		if err = validName(v.Title); err != nil {
			return nil, err
		}
		var folder int64
		if v.Folder != "" {
			if err = validName(v.Folder); err != nil {
				return nil, err
			}
			folder = folderIDs[v.Folder]
			if folder == 0 {
				r, e := tx.Exec("INSERT INTO folders(name,position,expanded) VALUES(?,(SELECT COALESCE(MAX(position),0)+1 FROM folders),1)", v.Folder)
				if e != nil {
					return nil, e
				}
				folder, e = r.LastInsertId()
				if e != nil {
					return nil, e
				}
				folderIDs[v.Folder] = folder
			}
		}
		if _, err = tx.Exec("INSERT INTO feeds(folder_id,title,url,position) VALUES(?,?,?,(SELECT COALESCE(MAX(position),0)+1 FROM feeds))", nullableID(folder), v.Title, v.URL); err != nil {
			return nil, err
		}
		added++
	}
	if err = tx.Commit(); err != nil {
		return nil, err
	}
	return map[string]int{"added": added, "skipped": skipped}, nil
}
func (s *Store) ExportOPML() (string, error) {
	folders, err := s.Folders()
	if err != nil {
		return "", err
	}
	feeds, err := s.Feeds()
	if err != nil {
		return "", err
	}
	doc := OPML{Version: "2.0", Title: "FeedAstrolabe Local"}
	for _, folder := range folders {
		o := Outline{Text: folder.Name}
		for _, f := range feeds {
			if f.FolderID == folder.ID && !strings.HasPrefix(f.URL, "social:") {
				o.Children = append(o.Children, Outline{Text: f.Title, Title: f.Title, Type: "rss", URL: f.URL, Site: f.SiteURL})
			}
		}
		doc.Outlines = append(doc.Outlines, o)
	}
	for _, f := range feeds {
		if f.FolderID == 0 && !strings.HasPrefix(f.URL, "social:") {
			doc.Outlines = append(doc.Outlines, Outline{Text: f.Title, Title: f.Title, Type: "rss", URL: f.URL, Site: f.SiteURL})
		}
	}
	b, err := xml.MarshalIndent(doc, "", "  ")
	return xml.Header + strings.TrimSpace(string(b)) + "\n", err
}
